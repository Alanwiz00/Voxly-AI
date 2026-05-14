from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from db.postgres import init_db
from db.qdrant import ensure_collections
from api.routes import auth, users, topics, generate, content, persona


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        await _migrate_db()
        await _seed_admin_emails()
        print("✓ PostgreSQL connected")
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        print("  → Check DATABASE_URL in backend/.env")

    try:
        await ensure_collections()
        print("✓ Qdrant connected")
    except Exception as e:
        print(f"✗ Qdrant connection failed: {e}")
        print("  → Check QDRANT_URL and QDRANT_API_KEY in backend/.env")

    yield


async def _migrate_db() -> None:
    """Add new columns to existing tables without a full Alembic setup."""
    from db.postgres import engine
    async with engine.begin() as conn:
        for stmt in [
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS learned_style TEXT",
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS style_synthesized_at TIMESTAMPTZ",
        ]:
            await conn.execute(__import__("sqlalchemy").text(stmt))


async def _seed_admin_emails() -> None:
    if not settings.ADMIN_EMAILS.strip():
        return
    from sqlalchemy import select
    from db.postgres import AsyncSessionLocal
    from db.models.user import AllowedEmail

    emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    async with AsyncSessionLocal() as db:
        for email in emails:
            exists = await db.execute(select(AllowedEmail).where(AllowedEmail.email == email))
            if not exists.scalar_one_or_none():
                db.add(AllowedEmail(email=email, added_by="system"))
        await db.commit()


app = FastAPI(title="Content Generator API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(topics.router)
app.include_router(generate.router)
app.include_router(content.router)
app.include_router(persona.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
