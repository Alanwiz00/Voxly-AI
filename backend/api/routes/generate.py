from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from qdrant_client.models import Filter, FieldCondition, MatchValue
from api.deps import CurrentUser, DB
from db.models.topic import Topic
from db.models.persona import PersonaProfile
from db.models.content import GeneratedContent
from db.qdrant import search_points
from services.sentiment import get_embeddings
from services.persona import get_best_persona_context
from services.generator import generate_post_ideas, generate_long_form, generate_for_all_platforms
from services.ingest import ingest, IMAGE_EXTENSIONS, IMAGE_MIME_TYPES
from core.config import settings

router = APIRouter(prefix="/generate", tags=["generate"])

VALID_PLATFORMS = {"twitter", "instagram", "facebook", "telegram"}
VALID_CONTENT_TYPES = {"idea", "long_form", "thread", "article"}


class GenerateRequest(BaseModel):
    topic_id: int | None = None
    topic_name: str | None = None  # free-form if no saved topic
    platform: str
    content_type: str  # idea | long_form | thread | article
    idea_count: int = 4  # only for content_type=idea


async def _get_sentiment_context(topic_id: int | None, topic_name: str, user_id: int) -> str:
    if not topic_id:
        return ""
    query_emb = (await get_embeddings([topic_name]))[0]
    results = await search_points(
        settings.SENTIMENT_COLLECTION,
        query_emb,
        limit=6,
        filter_=Filter(must=[FieldCondition(key="topic_id", match=MatchValue(value=topic_id))]),
    )
    if not results:
        return ""
    lines = []
    for r in results:
        p = r["payload"]
        lines.append(f"- [{p.get('sentiment', 'neutral')}] {p.get('summary', '')} (source: {p.get('url', '')})")
    return "\n".join(lines)


@router.post("/")
async def generate(body: GenerateRequest, current_user: CurrentUser, db: DB):
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Choose from: {VALID_PLATFORMS}")
    if body.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid content_type. Choose from: {VALID_CONTENT_TYPES}")

    topic_name = body.topic_name or ""
    topic_id = body.topic_id

    if topic_id:
        result = await db.execute(select(Topic).where(Topic.id == topic_id, Topic.user_id == current_user.id))
        topic = result.scalar_one_or_none()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic_name = topic.name

    persona_context = await get_best_persona_context(current_user.id, topic_name)
    sentiment_context = await _get_sentiment_context(topic_id, topic_name, current_user.id)

    if body.content_type == "idea":
        formatted_list = await generate_post_ideas(
            topic=topic_name,
            platform=body.platform,
            persona_context=persona_context,
            sentiment_context=sentiment_context,
            count=body.idea_count,
        )
        records = []
        for f in formatted_list:
            record = GeneratedContent(
                user_id=current_user.id,
                topic_id=topic_id,
                platform=body.platform,
                content_type="idea",
                title=f.meta.get("title", ""),
                content=f.body,
                meta=f.meta,
                version=1,
            )
            db.add(record)
            records.append(record)
        await db.commit()
        for r in records:
            await db.refresh(r)
        return {"content_type": "idea", "results": [_serialize(r) for r in records]}

    else:
        formatted = await generate_long_form(
            topic=topic_name,
            platform=body.platform,
            content_type=body.content_type,
            persona_context=persona_context,
            sentiment_context=sentiment_context,
        )
        record = GeneratedContent(
            user_id=current_user.id,
            topic_id=topic_id,
            platform=body.platform,
            content_type=body.content_type,
            title=formatted.meta.get("title", ""),
            content=formatted.body,
            meta=formatted.meta,
            version=1,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return {"content_type": body.content_type, "results": [_serialize(record)]}


@router.post("/from-source")
async def generate_from_source(
    current_user: CurrentUser,
    db: DB,
    platform: str = Form(...),
    content_type: str = Form(...),
    text: str | None = Form(None),
    url: str | None = Form(None),
    file: UploadFile | None = File(None),
    idea_count: int = Form(4),
):
    file_bytes = await file.read() if file else None
    file_type = None
    mime_type = None
    if file:
        import os
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext == ".pdf":
            file_type = "pdf"
        elif ext == ".docx":
            file_type = "docx"
        elif ext in IMAGE_EXTENSIONS:
            file_type = "image"
            mime_type = IMAGE_MIME_TYPES.get(ext, "image/jpeg")

    source_text = await ingest(text=text, file_bytes=file_bytes, file_type=file_type, mime_type=mime_type, url=url)
    if not source_text:
        raise HTTPException(status_code=400, detail="Could not extract content from the provided source.")

    topic_name = f"Custom source ({(url or file.filename if file else 'text')[:60]})"
    persona_context = await get_best_persona_context(current_user.id, topic_name)

    if content_type == "idea":
        formatted_list = await generate_post_ideas(
            topic=topic_name,
            platform=platform,
            persona_context=persona_context,
            sentiment_context=f"Reference content:\n{source_text[:2000]}",
            count=idea_count,
        )
        records = []
        for f in formatted_list:
            record = GeneratedContent(
                user_id=current_user.id,
                platform=platform,
                content_type="idea",
                title=f.meta.get("title", ""),
                content=f.body,
                meta=f.meta,
                version=1,
            )
            db.add(record)
            records.append(record)
        await db.commit()
        for r in records:
            await db.refresh(r)
        return {"content_type": "idea", "results": [_serialize(r) for r in records]}
    else:
        formatted = await generate_long_form(
            topic=topic_name,
            platform=platform,
            content_type=content_type,
            persona_context=persona_context,
            sentiment_context=f"Reference content:\n{source_text[:2000]}",
        )
        record = GeneratedContent(
            user_id=current_user.id,
            platform=platform,
            content_type=content_type,
            title=formatted.meta.get("title", ""),
            content=formatted.body,
            meta=formatted.meta,
            version=1,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return {"content_type": content_type, "results": [_serialize(record)]}


class BatchGenerateRequest(BaseModel):
    topic_id: int | None = None
    topic_name: str | None = None
    content_type: str  # idea | long_form | thread | article


@router.post("/batch")
async def generate_batch(body: BatchGenerateRequest, current_user: CurrentUser, db: DB):
    """Generate content for all four platforms in one request."""
    if body.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid content_type. Choose from: {VALID_CONTENT_TYPES}")

    topic_name = body.topic_name or ""
    if body.topic_id:
        result = await db.execute(select(Topic).where(Topic.id == body.topic_id, Topic.user_id == current_user.id))
        topic = result.scalar_one_or_none()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic_name = topic.name

    persona_context = await get_best_persona_context(current_user.id, topic_name)
    sentiment_context = await _get_sentiment_context(body.topic_id, topic_name, current_user.id)

    platform_results = await generate_for_all_platforms(
        topic=topic_name,
        content_type=body.content_type,
        persona_context=persona_context,
        sentiment_context=sentiment_context,
    )

    records = []
    for platform, formatted in platform_results.items():
        record = GeneratedContent(
            user_id=current_user.id,
            topic_id=body.topic_id,
            platform=platform,
            content_type=body.content_type,
            title=formatted.meta.get("title", topic_name),
            content=formatted.body,
            meta=formatted.meta,
            version=1,
        )
        db.add(record)
        records.append(record)

    await db.commit()
    for r in records:
        await db.refresh(r)

    return {
        "content_type": body.content_type,
        "results": {r.platform: _serialize(r) for r in records},
    }


def _serialize(record: GeneratedContent) -> dict:
    return {
        "id": record.id,
        "platform": record.platform,
        "content_type": record.content_type,
        "title": record.title,
        "content": record.content,
        "meta": record.meta,
        "version": record.version,
        "created_at": record.created_at.isoformat(),
    }
