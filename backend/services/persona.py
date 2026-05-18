import uuid
from collections import defaultdict
from pydantic import BaseModel
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from db.qdrant import upsert_points, search_points, delete_by_payload
from services.sentiment import get_embeddings
from core.config import settings


class PersonaData(BaseModel):
    niche: str | None = None
    target_audience: str | None = None
    tone: str | None = None
    brand_voice: str | None = None
    writing_style_notes: str | None = None
    sample_content: str | None = None


def _build_persona_text(data: PersonaData, learned_style: str | None = None) -> list[str]:
    chunks = []
    if data.niche:
        chunks.append(f"Niche: {data.niche}")
    if data.target_audience:
        chunks.append(f"Target audience: {data.target_audience}")
    if data.tone:
        chunks.append(f"Tone: {data.tone}")
    if data.brand_voice:
        chunks.append(f"Brand voice: {data.brand_voice}")
    if data.writing_style_notes:
        chunks.append(f"Writing style: {data.writing_style_notes}")
    if data.sample_content:
        samples = [data.sample_content[i:i+500] for i in range(0, len(data.sample_content), 500)]
        chunks.extend(samples[:6])
    if learned_style:
        chunks.insert(0, f"Learned style preferences (inferred from edit history):\n{learned_style}")
    return chunks


async def embed_persona(persona_id: int, user_id: int, data: PersonaData, learned_style: str | None = None) -> None:
    """Embed a single persona — replaces only that persona's vectors in Qdrant."""
    await delete_by_payload(settings.PERSONA_COLLECTION, "persona_id", persona_id)

    chunks = _build_persona_text(data, learned_style)
    if not chunks:
        return

    embeddings = await get_embeddings(chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"user_id": user_id, "persona_id": persona_id, "chunk": chunk},
        )
        for chunk, emb in zip(chunks, embeddings)
    ]
    await upsert_points(settings.PERSONA_COLLECTION, points)


async def get_best_persona_context(user_id: int, query: str, top_k: int = 12) -> str:
    """
    Finds the persona that best matches the query by semantic similarity,
    then returns its full chunk context.

    Strategy: retrieve top_k chunks from all user personas → group by persona_id
    → pick the persona with the highest cumulative score → return its chunks.
    Falls back to the default persona, then to the first available one.
    """
    query_embedding = (await get_embeddings([query]))[0]
    results = await search_points(
        settings.PERSONA_COLLECTION,
        query_embedding,
        limit=top_k,
        filter_=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
    )
    if not results:
        return ""

    # Accumulate scores per persona
    scores: dict[int, float] = defaultdict(float)
    chunks_by_persona: dict[int, list[str]] = defaultdict(list)
    for r in results:
        pid = r["payload"].get("persona_id")
        if pid is not None:
            scores[pid] += r["score"]
            chunks_by_persona[pid].append(r["payload"]["chunk"])

    if not scores:
        return "\n".join(r["payload"]["chunk"] for r in results)

    best_persona_id = max(scores, key=lambda pid: scores[pid])
    return "\n".join(chunks_by_persona[best_persona_id])


async def get_persona_context_by_id(persona_id: int, query: str, top_k: int = 5) -> str:
    """Retrieve context chunks for a specific persona."""
    query_embedding = (await get_embeddings([query]))[0]
    results = await search_points(
        settings.PERSONA_COLLECTION,
        query_embedding,
        limit=top_k,
        filter_=Filter(must=[FieldCondition(key="persona_id", match=MatchValue(value=persona_id))]),
    )
    return "\n".join(r["payload"]["chunk"] for r in results)
