import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Ensure /app is on the path for prefork child processes
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from celery import Celery
from qdrant_client.models import PointStruct

from core.config import settings
from db.postgres import AsyncSessionLocal
from db.models.topic import Topic, CrawlResult
from db.models.content import GeneratedContent
from db.qdrant import upsert_points, delete_by_payload
from services.crawl import crawl_topic
from services.sentiment import summarize_and_analyze, get_embeddings
from services.persona import get_best_persona_context
from services.generator import generate_reusable_ideas, generate_reusable_longform

celery_app = Celery("content_generator", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "crawl-all-topics": {
            "task": "workers.crawl_worker.crawl_all_active_topics",
            "schedule": timedelta(hours=settings.CRAWL_INTERVAL_HOURS),
        }
    },
)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="workers.crawl_worker.crawl_topic_task", bind=True, max_retries=3)
def crawl_topic_task(self, topic_id: int, topic_name: str, keywords: str | None, user_id: int):
    try:
        _run(_crawl_and_store(topic_id, topic_name, keywords, user_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="workers.crawl_worker.crawl_all_active_topics",
    bind=True,
    max_retries=3,
)
def crawl_all_active_topics(self):
    try:
        _run(_dispatch_all_topics())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)


async def _dispatch_all_topics():
    """
    Dispatch active topics in small batches with a gap between each batch so
    the worker pool never gets flooded all at once.

    Topics are ordered oldest-crawled-first so stale topics always get
    priority. Topics crawled within the last 75% of the interval are skipped
    to avoid unnecessary duplicate work on short restarts.
    """
    import random
    from sqlalchemy import select

    min_age = timedelta(hours=settings.CRAWL_INTERVAL_HOURS * 0.75)
    cutoff  = datetime.now(timezone.utc) - min_age

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Topic)
            .where(Topic.is_active == True)
            .where(
                (Topic.last_crawled_at == None) |
                (Topic.last_crawled_at < cutoff)
            )
            .order_by(Topic.last_crawled_at.asc().nullsfirst())
        )
        topics = result.scalars().all()

    batch_size = settings.CRAWL_BATCH_SIZE
    gap_secs   = settings.CRAWL_BATCH_GAP_SECS

    for batch_index, i in enumerate(range(0, len(topics), batch_size)):
        batch = topics[i : i + batch_size]
        # Base delay for this batch + small random jitter (±30 s) per task
        base_delay = batch_index * gap_secs
        for topic in batch:
            jitter = random.randint(-30, 30)
            crawl_topic_task.apply_async(
                args=[topic.id, topic.name, topic.keywords, topic.user_id],
                countdown=max(0, base_delay + jitter),
            )


async def _crawl_and_store(topic_id: int, topic_name: str, keywords: str | None, user_id: int):
    from sqlalchemy import update

    raw_results = await crawl_topic(topic_name, keywords)
    if not raw_results:
        return

    points: list[PointStruct] = []
    crawl_records: list[CrawlResult] = []
    enriched: list[dict] = []  # in-memory; carries key_facts + dates for the generator

    for item in raw_results:
        analysis = await summarize_and_analyze(topic_name, item["content"], source_date=item.get("date"))
        summary = analysis.get("summary", "")
        themes = ", ".join(analysis.get("key_themes", []))
        article_date = analysis.get("article_date") or item.get("date") or datetime.now(timezone.utc).date().isoformat()

        chunk_text = f"Summary: {summary}\nThemes: {themes}"
        embeddings = await get_embeddings([chunk_text])

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embeddings[0],
                payload={
                    "topic_id": topic_id,
                    "user_id": user_id,
                    "url": item["url"],
                    "summary": summary,
                    "themes": themes,
                    "sentiment": analysis.get("sentiment", "neutral"),
                    "article_date": article_date,
                    "source": item.get("source", "web"),
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

        crawl_records.append(
            CrawlResult(
                topic_id=topic_id,
                url=item["url"],
                content_summary=summary,
                sentiment_score=analysis.get("vader_score", 0.0),
                sentiment_label=analysis.get("vader_label", "neutral"),
            )
        )

        enriched.append({
            "url": item["url"],
            "date": article_date,
            "source": item.get("source", "web"),
            "sentiment": analysis.get("vader_label", "neutral"),
            "summary": summary,
            "key_facts": analysis.get("key_facts", []),
        })

    await delete_by_payload(settings.SENTIMENT_COLLECTION, "topic_id", topic_id)
    await upsert_points(settings.SENTIMENT_COLLECTION, points)

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Topic).where(Topic.id == topic_id).values(last_crawled_at=datetime.now(timezone.utc))
        )
        db.add_all(crawl_records)
        await db.commit()

    # Auto-generate reusable content using enriched source data
    await _generate_reusable_for_topic(topic_id, topic_name, user_id, enriched)


def _build_sentiment_context(enriched: list[dict]) -> str:
    """
    Build a structured reference block for the generator from crawl results.
    Includes source URL, publication date, sentiment, summary, and verbatim facts.
    """
    parts = []
    for e in enriched:
        facts = e.get("key_facts") or []
        if facts:
            fact_lines = "\n    ".join(f"• {f}" for f in facts)
        else:
            fact_lines = "(no specific statistics or figures found in this source)"
        parts.append(
            f"[{e['date']}] [{e['sentiment']}] {e['source'].upper()} — {e['url']}\n"
            f"  Summary: {e['summary']}\n"
            f"  Verified facts from source:\n    {fact_lines}"
        )
    return "\n\n".join(parts)


async def _generate_reusable_for_topic(
    topic_id: int,
    topic_name: str,
    user_id: int,
    enriched: list[dict],
):
    sentiment_context = _build_sentiment_context(enriched)
    persona_context = await get_best_persona_context(user_id, topic_name)

    ideas = await generate_reusable_ideas(
        topic=topic_name,
        persona_context=persona_context,
        sentiment_context=sentiment_context,
    )
    longform = await generate_reusable_longform(
        topic=topic_name,
        persona_context=persona_context,
        sentiment_context=sentiment_context,
    )

    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete as sa_delete
        # Remove stale auto-generated content for this topic before inserting fresh
        await db.execute(
            sa_delete(GeneratedContent).where(
                GeneratedContent.topic_id == topic_id,
                GeneratedContent.platform == "general",
            )
        )
        for f in ideas:
            db.add(GeneratedContent(
                user_id=user_id,
                topic_id=topic_id,
                platform="general",
                content_type="idea",
                title=f.meta.get("title", ""),
                content=f.body,
                meta=f.meta,
                version=1,
            ))
        db.add(GeneratedContent(
            user_id=user_id,
            topic_id=topic_id,
            platform="general",
            content_type="long_form",
            title=longform.meta.get("title", ""),
            content=longform.body,
            meta=longform.meta,
            version=1,
        ))
        await db.commit()
