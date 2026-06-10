from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from db.postgres import init_db
from db.qdrant import ensure_collections
from api.routes import auth, users, topics, generate, content, persona, api_keys, analyze


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
            "ALTER TABLE persona_profiles ALTER COLUMN tone TYPE TEXT",
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS learned_style TEXT",
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS style_synthesized_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS name VARCHAR(255) DEFAULT 'Default'",
            "ALTER TABLE persona_profiles ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE",
            "ALTER TABLE persona_profiles DROP CONSTRAINT IF EXISTS persona_profiles_user_id_key",
            # Mark existing single personas as default (initial migration)
            "UPDATE persona_profiles SET is_default = TRUE WHERE is_default = FALSE",
            # Fix: if multiple personas per user are all marked default, keep only the oldest one
            """
            UPDATE persona_profiles
            SET is_default = FALSE
            WHERE is_default = TRUE
              AND id NOT IN (
                SELECT MIN(id) FROM persona_profiles GROUP BY user_id
              )
            """,
            "ALTER TABLE generated_content ADD COLUMN IF NOT EXISTS rating SMALLINT",
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                key_hash VARCHAR(64) NOT NULL UNIQUE,
                key_prefix VARCHAR(16) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                last_used_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
        ]:
            await conn.execute(__import__("sqlalchemy").text(stmt))


async def _seed_admin_emails() -> None:
    if not settings.ADMIN_EMAILS.strip():
        return
    from sqlalchemy import select, update
    from db.postgres import AsyncSessionLocal
    from db.models.user import AllowedEmail, User

    emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    async with AsyncSessionLocal() as db:
        for email in emails:
            # Ensure email is in the allowlist
            exists = await db.execute(select(AllowedEmail).where(AllowedEmail.email == email))
            if not exists.scalar_one_or_none():
                db.add(AllowedEmail(email=email, added_by="system"))
            # If the user already exists, make sure they have is_admin=True
            await db.execute(update(User).where(User.email == email).values(is_admin=True))
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
app.include_router(api_keys.router)
app.include_router(analyze.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
