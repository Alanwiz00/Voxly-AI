from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.postgres import get_db
from db.models.user import AllowedEmail
from core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/check-access")
async def check_access(
    email: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Server-to-server endpoint used by Next.js during OAuth sign-in.
    Requires X-Internal-Secret matching NEXTAUTH_SECRET — no user JWT needed.
    Returns 200 if the email is in the allowlist, 403 if not.
    """
    secret = request.headers.get("X-Internal-Secret", "")
    if not secret or secret != settings.NEXTAUTH_SECRET:
        raise HTTPException(status_code=401, detail="Invalid internal secret")

    result = await db.execute(select(AllowedEmail).where(AllowedEmail.email == email))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Email not in allowlist")

    return {"allowed": True}
