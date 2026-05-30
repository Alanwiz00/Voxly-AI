import asyncio
import sys
import uuid
from datetime import datetime, timezone

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
        "crawl-all-topics-every-6h": {
            "task": "workers.crawl_worker.crawl_all_active_topics",
            "schedule": settings.CRAWL_INTERVAL_HOURS * 3600,
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


@celery_app.task(name="workers.crawl_worker.crawl_all_active_topics")
def crawl_all_active_topics():
    _run(_dispatch_all_topics())


async def _dispatch_all_topics():
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Topic).where(Topic.is_active == True))
        for topic in result.scalars().all():
            crawl_topic_task.delay(topic.id, topic.name, topic.keywords, topic.user_id)


async def _crawl_and_store(topic_id: int, topic_name: str, keywords: str | None, user_id: int):
    from sqlalchemy import select, update

    raw_results = await crawl_topic(topic_name, keywords)
    if not raw_results:
        return

    points: list[PointStruct] = []
    crawl_records: list[CrawlResult] = []

    for item in raw_results:
        analysis = await summarize_and_analyze(topic_name, item["content"])
        summary = analysis.get("summary", "")
        themes = ", ".join(analysis.get("key_themes", []))
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

    await delete_by_payload(settings.SENTIMENT_COLLECTION, "topic_id", topic_id)
    await upsert_points(settings.SENTIMENT_COLLECTION, points)

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Topic).where(Topic.id == topic_id).values(last_crawled_at=datetime.now(timezone.utc))
        )
        db.add_all(crawl_records)
        await db.commit()

    # Auto-generate reusable content from the fresh crawl data
    await _generate_reusable_for_topic(topic_id, topic_name, user_id, crawl_records)


async def _generate_reusable_for_topic(
    topic_id: int,
    topic_name: str,
    user_id: int,
    crawl_records: list[CrawlResult],
):
    sentiment_context = "\n".join(
        f"- [{r.sentiment_label}] {r.content_summary}"
        for r in crawl_records
        if r.content_summary
    )
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
