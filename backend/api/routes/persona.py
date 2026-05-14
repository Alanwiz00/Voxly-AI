from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from api.deps import CurrentUser, DB
from db.models.persona import PersonaProfile
from services.persona import PersonaData, embed_persona
from services.style_synthesis import run_synthesis_and_save

router = APIRouter(prefix="/persona", tags=["persona"])


class PersonaResponse(BaseModel):
    id: int
    niche: str | None
    target_audience: str | None
    tone: str | None
    brand_voice: str | None
    writing_style_notes: str | None
    sample_content: str | None
    learned_style: str | None
    style_synthesized_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_ext(cls, p: PersonaProfile) -> "PersonaResponse":
        return cls(
            id=p.id,
            niche=p.niche,
            target_audience=p.target_audience,
            tone=p.tone,
            brand_voice=p.brand_voice,
            writing_style_notes=p.writing_style_notes,
            sample_content=p.sample_content,
            learned_style=p.learned_style,
            style_synthesized_at=p.style_synthesized_at.isoformat() if p.style_synthesized_at else None,
        )


@router.get("/", response_model=PersonaResponse | None)
async def get_persona(current_user: CurrentUser, db: DB):
    result = await db.execute(select(PersonaProfile).where(PersonaProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    return PersonaResponse.from_orm_ext(profile) if profile else None


@router.put("/", response_model=PersonaResponse)
async def upsert_persona(body: PersonaData, current_user: CurrentUser, db: DB):
    result = await db.execute(select(PersonaProfile).where(PersonaProfile.user_id == current_user.id))
    persona = result.scalar_one_or_none()

    if persona is None:
        persona = PersonaProfile(user_id=current_user.id, **body.model_dump(exclude_none=True))
        db.add(persona)
    else:
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(persona, k, v)

    await db.commit()
    await db.refresh(persona)

    # Re-embed keeping any existing learned style intact
    await embed_persona(current_user.id, body, learned_style=persona.learned_style)
    return PersonaResponse.from_orm_ext(persona)


@router.post("/synthesize-style", response_model=PersonaResponse)
async def synthesize_style(current_user: CurrentUser, db: DB):
    """Run a full style synthesis pass over edit history and update the persona."""
    style_summary = await run_synthesis_and_save(current_user.id)
    if style_summary is None:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough edit history yet — make at least 3 re-edits first.",
        )

    result = await db.execute(select(PersonaProfile).where(PersonaProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    return PersonaResponse.from_orm_ext(profile)
