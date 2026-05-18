import json
from datetime import datetime, timezone
from openai import AsyncOpenAI
from core.config import settings
from services.sentiment import get_openai

MIN_EDITS_REQUIRED = 3
MAX_EDITS_SAMPLED = 30


async def synthesize_user_style(user_id: int) -> str | None:
    """
    Reads the user's re-edit history, runs an LLM pass to distill consistent
    style preferences, and returns a bullet-point style profile string.
    Returns None if there is not enough edit history yet.
    """
    from sqlalchemy import select
    from db.postgres import AsyncSessionLocal
    from db.models.content import ContentVersion, GeneratedContent

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(ContentVersion, GeneratedContent)
            .join(GeneratedContent, ContentVersion.content_id == GeneratedContent.id)
            .where(GeneratedContent.user_id == user_id)
            .order_by(ContentVersion.created_at.desc())
            .limit(MAX_EDITS_SAMPLED)
        )
        pairs = rows.all()

    if len(pairs) < MIN_EDITS_REQUIRED:
        return None

    # Build edit history text — only pairs that have an instruction
    history_items = [
        (version, original)
        for version, original in pairs
        if version.edit_instruction and version.edit_instruction.strip()
    ]
    if len(history_items) < MIN_EDITS_REQUIRED:
        return None

    history_text = "\n\n".join(
        f"{i + 1}. Instruction: \"{h.edit_instruction}\"\n"
        f"   Before: {orig.content[:300]}{'...' if len(orig.content) > 300 else ''}\n"
        f"   After: {h.content[:300]}{'...' if len(h.content) > 300 else ''}"
        for i, (h, orig) in enumerate(history_items)
    )

    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_SENTIMENT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a writing style analyst. Analyze editing patterns and distill them into a "
                    "concise, actionable style guide another writer can follow precisely."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here are {len(history_items)} editing patterns from a content creator:\n\n"
                    f"{history_text}\n\n"
                    "Extract 5-8 specific, actionable style preferences. Focus on:\n"
                    "- Sentence length and rhythm\n"
                    "- Tone (formal vs casual, direct vs narrative, personal vs authoritative)\n"
                    "- What they consistently add (humor, data, questions, analogies, stories)\n"
                    "- What they consistently remove or avoid (jargon, passive voice, hedging, filler)\n"
                    "- Structural patterns (how they open, close, use lists)\n\n"
                    "Be specific — not 'uses casual tone' but 'uses contractions and first-person anecdotes'.\n\n"
                    'Return JSON: {"style_summary": "• preference 1\\n• preference 2\\n..."}'
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=512,
    )

    data = json.loads(response.choices[0].message.content)
    return data.get("style_summary") or None


async def run_synthesis_and_save(user_id: int, persona_id: int | None = None) -> str | None:
    """
    Full pipeline: synthesize style → save to DB → re-embed persona.
    Returns the new style summary, or None if skipped.
    """
    from sqlalchemy import select
    from db.postgres import AsyncSessionLocal
    from db.models.persona import PersonaProfile
    from services.persona import PersonaData, embed_persona

    style_summary = await synthesize_user_style(user_id)
    if not style_summary:
        return None

    async with AsyncSessionLocal() as db:
        # Target a specific persona or fall back to the default / first
        if persona_id:
            result = await db.execute(
                select(PersonaProfile).where(PersonaProfile.id == persona_id, PersonaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
        else:
            result = await db.execute(
                select(PersonaProfile)
                .where(PersonaProfile.user_id == user_id)
                .order_by(PersonaProfile.is_default.desc(), PersonaProfile.created_at.asc())
                .limit(1)
            )
            profile = result.scalar_one_or_none()

        if profile is None:
            profile = PersonaProfile(
                user_id=user_id,
                name="Default",
                is_default=True,
                learned_style=style_summary,
                style_synthesized_at=datetime.now(timezone.utc),
            )
            db.add(profile)
        else:
            profile.learned_style = style_summary
            profile.style_synthesized_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(profile)

        persona_data = PersonaData(
            niche=profile.niche,
            target_audience=profile.target_audience,
            tone=profile.tone,
            brand_voice=profile.brand_voice,
            writing_style_notes=profile.writing_style_notes,
            sample_content=profile.sample_content,
        )
        saved_persona_id = profile.id

    await embed_persona(saved_persona_id, user_id, persona_data, learned_style=style_summary)
    return style_summary
