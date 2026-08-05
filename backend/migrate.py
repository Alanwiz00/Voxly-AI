"""
One-shot migration script — run once to apply schema changes that create_all misses
on already-existing tables.

Usage (inside the backend container or locally with DB access):
    python migrate.py
"""
import asyncio
from sqlalchemy import text
from db.postgres import engine


MIGRATIONS = [
    # Add monthly_token_limit to users (idempotent)
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS monthly_token_limit INTEGER;
    """,

    # Create user_token_usage table (idempotent)
    """
    CREATE TABLE IF NOT EXISTS user_token_usage (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        year_month VARCHAR(7) NOT NULL,
        tokens_used INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_user_token_month UNIQUE (user_id, year_month)
    );
    """,

    # Index for fast per-user lookups
    """
    CREATE INDEX IF NOT EXISTS ix_user_token_usage_user_id
    ON user_token_usage (user_id);
    """,
]


async def run():
    async with engine.begin() as conn:
        for sql in MIGRATIONS:
            await conn.execute(text(sql.strip()))
            print(f"OK: {sql.strip()[:60]}...")
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
