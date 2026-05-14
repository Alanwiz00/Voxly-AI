from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from db.postgres import get_db
from db.models.user import User, AllowedEmail

bearer = HTTPBearer()
ALGORITHM = "HS256"


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.NEXTAUTH_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_token(credentials.credentials)
    email: str | None = payload.get("email")
    name: str | None = payload.get("name")

    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    # Verify email is in the allowlist
    allowed = await db.execute(select(AllowedEmail).where(AllowedEmail.email == email))
    if not allowed.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email is not authorized to access this application",
        )

    # Get or auto-create the user on first login
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=email, name=name or "")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user


# Convenience type aliases used across routes
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
