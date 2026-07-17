import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from api.deps import CurrentUser, DB
from db.models.api_key import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _generate_key() -> tuple[str, str, str]:
    """Returns (full_key, key_hash, key_prefix)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"vlx-{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:13]  # "vlx-" + 9 chars
    return full_key, key_hash, key_prefix


class CreateKeyRequest(BaseModel):
    name: str  # human label, e.g. "MCP Server" or "Fetch.ai Agent"


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: str | None
    created_at: str
    # full_key only present on creation
    key: str | None = None


def _serialize(k: ApiKey, full_key: str | None = None) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=k.id,
        name=k.name,
        key_prefix=k.key_prefix,
        is_active=k.is_active,
        last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
        created_at=k.created_at.isoformat(),
        key=full_key,
    )


@router.post("/", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(body: CreateKeyRequest, current_user: CurrentUser, db: DB):
    """Create a new API key. The full key is returned once — store it securely."""
    full_key, key_hash, key_prefix = _generate_key()
    record = ApiKey(
        user_id=current_user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _serialize(record, full_key=full_key)


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(current_user: CurrentUser, db: DB):
    """List all API keys belonging to the current user (prefixes only, never full keys)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return [_serialize(k) for k in result.scalars().all()]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: int, current_user: CurrentUser, db: DB):
    """Permanently revoke an API key."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(record)
    await db.commit()
