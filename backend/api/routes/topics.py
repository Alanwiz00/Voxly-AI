from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, delete, desc
from api.deps import CurrentUser, DB
from db.models.topic import Topic, CrawlResult
from db.models.content import GeneratedContent

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicCreate(BaseModel):
    name: str
    keywords: str | None = None
    description: str | None = None


class TopicResponse(BaseModel):
    id: int
    name: str
    keywords: str | None
    description: str | None
    is_active: bool
    last_crawled_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_ext(cls, topic: Topic):
        return cls(
            id=topic.id,
            name=topic.name,
            keywords=topic.keywords,
            description=topic.description,
            is_active=topic.is_active,
            last_crawled_at=topic.last_crawled_at.isoformat() if topic.last_crawled_at else None,
        )


@router.get("/", response_model=list[TopicResponse])
async def list_topics(current_user: CurrentUser, db: DB):
    result = await db.execute(select(Topic).where(Topic.user_id == current_user.id))
    return [TopicResponse.from_orm_ext(t) for t in result.scalars()]


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TopicResponse)
async def create_topic(body: TopicCreate, current_user: CurrentUser, db: DB, background_tasks: BackgroundTasks):
    topic = Topic(user_id=current_user.id, **body.model_dump())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    # Trigger initial crawl immediately in background
    background_tasks.add_task(_trigger_crawl, topic.id, topic.name, topic.keywords, current_user.id)
    return TopicResponse.from_orm_ext(topic)


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(topic_id: int, body: TopicCreate, current_user: CurrentUser, db: DB):
    result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(topic, k, v)
    await db.commit()
    await db.refresh(topic)
    return TopicResponse.from_orm_ext(topic)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(topic_id: int, current_user: CurrentUser, db: DB):
    await db.execute(delete(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    await db.commit()


@router.post("/{topic_id}/crawl")
async def trigger_crawl(topic_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    from workers.crawl_worker import _crawl_and_store
    await _crawl_and_store(topic.id, topic.name, topic.keywords, current_user.id)
    return {"message": "Crawl complete", "topic_id": topic_id}


@router.get("/{topic_id}/crawl-results")
async def get_crawl_results(topic_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Topic not found")

    rows = await db.execute(
        select(CrawlResult).where(CrawlResult.topic_id == topic_id).order_by(CrawlResult.crawled_at.desc()).limit(20)
    )
    return [
        {
            "url": r.url,
            "summary": r.content_summary,
            "sentiment_score": r.sentiment_score,
            "sentiment_label": r.sentiment_label,
            "crawled_at": r.crawled_at.isoformat(),
        }
        for r in rows.scalars()
    ]


@router.get("/{topic_id}/content")
async def get_topic_content(topic_id: int, current_user: CurrentUser, db: DB):
    """Return the latest auto-generated reusable content for this topic."""
    result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Topic not found")

    rows = await db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.topic_id == topic_id,
            GeneratedContent.user_id == current_user.id,
            GeneratedContent.platform == "general",
            GeneratedContent.parent_id == None,
        )
        .order_by(desc(GeneratedContent.created_at))
        .limit(10)
    )
    return [_serialize_content(r) for r in rows.scalars()]


def _serialize_content(r: GeneratedContent) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "content_type": r.content_type,
        "title": r.title,
        "content": r.content,
        "meta": r.meta,
        "version": r.version,
        "created_at": r.created_at.isoformat(),
    }


async def _trigger_crawl(topic_id: int, topic_name: str, keywords: str | None, user_id: int):
    from workers.crawl_worker import _crawl_and_store
    await _crawl_and_store(topic_id, topic_name, keywords, user_id)
