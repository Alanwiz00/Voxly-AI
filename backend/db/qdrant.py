from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchValue,
    PayloadSchemaType, PointStruct, VectorParams,
)
from core.config import settings

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return _client


async def ensure_collections() -> None:
    client = get_qdrant()
    existing = {c.name for c in (await client.get_collections()).collections}

    for name in (settings.PERSONA_COLLECTION, settings.SENTIMENT_COLLECTION):
        if name not in existing:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=settings.OPENAI_EMBEDDING_DIM, distance=Distance.COSINE),
            )
        # Always ensure payload indexes exist (idempotent — Qdrant ignores if already present)
        await client.create_payload_index(
            collection_name=name,
            field_name="user_id",
            field_schema=PayloadSchemaType.INTEGER,
        )

    # persona_id index for per-persona embed/delete
    await client.create_payload_index(
        collection_name=settings.PERSONA_COLLECTION,
        field_name="persona_id",
        field_schema=PayloadSchemaType.INTEGER,
    )

    # topic_sentiment also filters on topic_id
    await client.create_payload_index(
        collection_name=settings.SENTIMENT_COLLECTION,
        field_name="topic_id",
        field_schema=PayloadSchemaType.INTEGER,
    )


async def upsert_points(collection: str, points: list[PointStruct]) -> None:
    await get_qdrant().upsert(collection_name=collection, points=points)


async def search_points(
    collection: str,
    vector: list[float],
    limit: int = 5,
    filter_: Filter | None = None,
) -> list[dict]:
    results = await get_qdrant().search(
        collection_name=collection,
        query_vector=vector,
        limit=limit,
        query_filter=filter_,
        with_payload=True,
    )
    return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]


async def delete_by_payload(collection: str, field: str, value: str | int) -> None:
    from qdrant_client.models import FilterSelector
    await get_qdrant().delete(
        collection_name=collection,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key=field, match=MatchValue(value=value))])
        ),
    )
