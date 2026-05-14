from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, delete
from api.deps import CurrentUser, DB
from db.models.user import AllowedEmail, User

router = APIRouter(prefix="/users", tags=["users"])


class AllowedEmailCreate(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None
    avatar_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return current_user


@router.get("/allowed-emails")
async def list_allowed_emails(current_user: CurrentUser, db: DB):
    result = await db.execute(select(AllowedEmail))
    return [{"id": r.id, "email": r.email, "added_by": r.added_by} for r in result.scalars()]


@router.post("/allowed-emails", status_code=status.HTTP_201_CREATED)
async def add_allowed_email(body: AllowedEmailCreate, current_user: CurrentUser, db: DB):
    existing = await db.execute(select(AllowedEmail).where(AllowedEmail.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already allowed")
    entry = AllowedEmail(email=body.email, added_by=current_user.email)
    db.add(entry)
    await db.commit()
    return {"email": body.email, "added_by": current_user.email}


@router.delete("/allowed-emails/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_allowed_email(email: str, current_user: CurrentUser, db: DB):
    await db.execute(delete(AllowedEmail).where(AllowedEmail.email == email))
    await db.commit()
