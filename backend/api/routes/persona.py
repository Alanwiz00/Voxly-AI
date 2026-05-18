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
    name: str
    is_default: bool
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
            name=p.name or "Default",
            is_default=p.is_default or False,
            niche=p.niche,
            target_audience=p.target_audience,
            tone=p.tone,
            brand_voice=p.brand_voice,
            writing_style_notes=p.writing_style_notes,
            sample_content=p.sample_content,
            learned_style=p.learned_style,
            style_synthesized_at=p.style_synthesized_at.isoformat() if p.style_synthesized_at else None,
        )


class PersonaCreate(PersonaData):
    name: str = "Default"


class PersonaUpdate(PersonaData):
    name: str | None = None


@router.get("/", response_model=list[PersonaResponse])
async def list_personas(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(PersonaProfile)
        .where(PersonaProfile.user_id == current_user.id)
        .order_by(PersonaProfile.is_default.desc(), PersonaProfile.created_at.asc())
    )
    return [PersonaResponse.from_orm_ext(p) for p in result.scalars().all()]


@router.post("/", response_model=PersonaResponse, status_code=201)
async def create_persona(body: PersonaCreate, current_user: CurrentUser, db: DB):
    # If this is the user's first persona, make it default automatically
    existing = await db.execute(select(PersonaProfile).where(PersonaProfile.user_id == current_user.id))
    is_first = existing.scalar_one_or_none() is None

    persona = PersonaProfile(
        user_id=current_user.id,
        name=body.name,
        is_default=is_first,
        **{k: v for k, v in body.model_dump(exclude={"name"}).items() if v is not None},
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    data = PersonaData(**body.model_dump(exclude={"name"}))
    await embed_persona(persona.id, current_user.id, data)
    return PersonaResponse.from_orm_ext(persona)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(persona_id: int, body: PersonaUpdate, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(PersonaProfile).where(PersonaProfile.id == persona_id, PersonaProfile.user_id == current_user.id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(persona, k, v)

    await db.commit()
    await db.refresh(persona)

    data = PersonaData(**{f: getattr(persona, f) for f in PersonaData.model_fields})
    await embed_persona(persona.id, current_user.id, data, learned_style=persona.learned_style)
    return PersonaResponse.from_orm_ext(persona)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(persona_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(PersonaProfile).where(PersonaProfile.id == persona_id, PersonaProfile.user_id == current_user.id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if persona.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default persona. Set another as default first.")

    from db.qdrant import delete_by_payload
    from core.config import settings
    await delete_by_payload(settings.PERSONA_COLLECTION, "persona_id", persona_id)

    await db.delete(persona)
    await db.commit()


@router.post("/{persona_id}/set-default", response_model=PersonaResponse)
async def set_default_persona(persona_id: int, current_user: CurrentUser, db: DB):
    # Unset all defaults for this user
    all_personas = await db.execute(
        select(PersonaProfile).where(PersonaProfile.user_id == current_user.id)
    )
    for p in all_personas.scalars().all():
        p.is_default = p.id == persona_id

    result = await db.execute(
        select(PersonaProfile).where(PersonaProfile.id == persona_id, PersonaProfile.user_id == current_user.id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    await db.commit()
    await db.refresh(persona)
    return PersonaResponse.from_orm_ext(persona)


@router.post("/{persona_id}/synthesize-style", response_model=PersonaResponse)
async def synthesize_style(persona_id: int, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(PersonaProfile).where(PersonaProfile.id == persona_id, PersonaProfile.user_id == current_user.id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    style_summary = await run_synthesis_and_save(current_user.id, persona_id)
    if style_summary is None:
        raise HTTPException(status_code=400, detail="Not enough edit history yet — make at least 3 re-edits first.")

    await db.refresh(persona)
    return PersonaResponse.from_orm_ext(persona)
