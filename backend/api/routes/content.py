from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from api.deps import CurrentUser, DB
from db.models.content import GeneratedContent, ContentVersion
from services.generator import re_edit_content, adapt_to_platform
from services.persona import get_persona_context

router = APIRouter(prefix="/content", tags=["content"])


class ReEditRequest(BaseModel):
    instruction: str


@router.get("/")
async def list_content(
    current_user: CurrentUser,
    db: DB,
    platform: str | None = Query(None),
    content_type: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
):
    query = select(GeneratedContent).where(
        GeneratedContent.user_id == current_user.id,
        GeneratedContent.parent_id == None,  # only top-level (non-re-edit children)
    )
    if platform:
        query = query.where(GeneratedContent.platform == platform)
    if content_type:
        query = query.where(GeneratedContent.content_type == content_type)
    query = query.order_by(desc(GeneratedContent.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    return [_serialize(r) for r in result.scalars()]


@router.get("/{content_id}")
async def get_content(content_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Content not found")

    versions = await db.execute(
        select(ContentVersion)
        .where(ContentVersion.content_id == content_id)
        .order_by(ContentVersion.version_number)
    )
    return {**_serialize(record), "versions": [_serialize_version(v) for v in versions.scalars()]}


@router.post("/{content_id}/re-edit")
async def re_edit(content_id: int, body: ReEditRequest, background_tasks: BackgroundTasks, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.user_id == current_user.id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Content not found")

    persona_context = await get_persona_context(current_user.id, original.title or original.content[:100])
    new_body = await re_edit_content(original.content, original.platform, body.instruction, persona_context)

    # Save as a new version linked to original
    new_version_num = original.version + 1
    version_record = ContentVersion(
        content_id=original.id,
        version_number=new_version_num,
        content=new_body,
        edit_instruction=body.instruction,
    )
    db.add(version_record)

    # Create a new content record as a child of the original
    new_record = GeneratedContent(
        user_id=current_user.id,
        topic_id=original.topic_id,
        platform=original.platform,
        content_type=original.content_type,
        title=original.title,
        content=new_body,
        meta=original.meta,
        parent_id=original.id,
        version=new_version_num,
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)

    # Auto-synthesize style every 5 re-edits
    count_result = await db.execute(
        select(func.count(ContentVersion.id))
        .join(GeneratedContent, ContentVersion.content_id == GeneratedContent.id)
        .where(GeneratedContent.user_id == current_user.id)
    )
    total_edits = count_result.scalar() or 0
    if total_edits >= 3 and total_edits % 5 == 0:
        from services.style_synthesis import run_synthesis_and_save
        background_tasks.add_task(run_synthesis_and_save, current_user.id)

    return _serialize(new_record)


class AdaptRequest(BaseModel):
    platform: str


VALID_PLATFORMS = {"twitter", "instagram", "facebook", "telegram"}


@router.post("/{content_id}/adapt")
async def adapt_content(content_id: int, body: AdaptRequest, current_user: CurrentUser, db: DB):
    """Adapt a general reusable post to a specific platform's format and tone."""
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform. Choose from: {VALID_PLATFORMS}")

    result = await db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.user_id == current_user.id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Content not found")

    persona_context = await get_persona_context(current_user.id, original.title or original.content[:100])
    formatted = await adapt_to_platform(
        content=original.content,
        title=original.title or "",
        platform=body.platform,
        persona_context=persona_context,
    )

    record = GeneratedContent(
        user_id=current_user.id,
        topic_id=original.topic_id,
        platform=body.platform,
        content_type=original.content_type,
        title=formatted.meta.get("title", original.title),
        content=formatted.body,
        meta=formatted.meta,
        parent_id=original.id,
        version=original.version + 1,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _serialize(record)


@router.delete("/{content_id}", status_code=204)
async def delete_content(content_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(record)
    await db.commit()


def _serialize(r: GeneratedContent) -> dict:
    return {
        "id": r.id,
        "platform": r.platform,
        "content_type": r.content_type,
        "title": r.title,
        "content": r.content,
        "meta": r.meta,
        "version": r.version,
        "parent_id": r.parent_id,
        "created_at": r.created_at.isoformat(),
    }


def _serialize_version(v: ContentVersion) -> dict:
    return {
        "version_number": v.version_number,
        "content": v.content,
        "edit_instruction": v.edit_instruction,
        "created_at": v.created_at.isoformat(),
    }
