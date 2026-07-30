import hashlib
from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from db.postgres import get_db
from db.models.user import User
from db.models.api_key import ApiKey
from db.models.token_usage import UserTokenUsage

bearer = HTTPBearer()
ALGORITHM = "HS256"


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.NEXTAUTH_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def _user_from_api_key(token: str, db: AsyncSession) -> User:
    """Resolve an sk-... API key to its owner and update last_used_at."""
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    # Update last_used_at without blocking the request
    record.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


async def _user_from_jwt(token: str, db: AsyncSession) -> User:
    """Resolve a JWT (Google OAuth via Auth.js) to its owner."""
    payload = decode_token(token)
    email: str | None = payload.get("email")
    name: str | None = payload.get("name")

    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    admin_emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    is_admin = email in admin_emails

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email, name=name or "", is_admin=is_admin)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif is_admin and not user.is_admin:
        user.is_admin = True
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credentials.credentials
    if token.startswith("vlx-"):
        return await _user_from_api_key(token, db)
    return await _user_from_jwt(token, db)


async def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# Convenience type aliases used across routes
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Token budget helpers
# ---------------------------------------------------------------------------

def _current_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def check_token_budget(user: User, db: AsyncSession) -> None:
    """Raise 429 if the user has exhausted their monthly token budget."""
    limit = user.monthly_token_limit if user.monthly_token_limit is not None else settings.DEFAULT_MONTHLY_TOKEN_LIMIT
    if limit == 0:
        return  # unlimited

    result = await db.execute(
        select(UserTokenUsage).where(
            UserTokenUsage.user_id == user.id,
            UserTokenUsage.year_month == _current_year_month(),
        )
    )
    usage = result.scalar_one_or_none()
    used = usage.tokens_used if usage else 0
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly token limit of {limit:,} reached. Resets on the 1st of next month.",
        )


async def record_token_usage(user_id: int, tokens: int, db: AsyncSession) -> None:
    """Upsert the monthly token counter for a user."""
    year_month = _current_year_month()
    stmt = (
        pg_insert(UserTokenUsage)
        .values(user_id=user_id, year_month=year_month, tokens_used=tokens)
        .on_conflict_do_update(
            constraint="uq_user_token_month",
            set_={"tokens_used": UserTokenUsage.tokens_used + tokens},
        )
    )
    await db.execute(stmt)
    await db.commit()
