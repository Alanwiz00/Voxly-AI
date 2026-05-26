from fastapi import APIRouter, HTTPException, Request
from core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/check-access")
async def check_access(
    email: str,
    request: Request,
):
    """
    Server-to-server endpoint used by Next.js during OAuth sign-in.
    Validates the internal secret; any authenticated Google user is allowed.
    """
    secret = request.headers.get("X-Internal-Secret", "")
    if not secret or secret != settings.NEXTAUTH_SECRET:
        raise HTTPException(status_code=401, detail="Invalid internal secret")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    return {"allowed": True}
