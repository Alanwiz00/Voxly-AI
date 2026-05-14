from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.APP_ENV == "development")
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Register all models with the mapper immediately so relationship strings
# (e.g. "User" in Topic.user) resolve in any process that imports this module.
import db.models.user  # noqa: E402, F401
import db.models.persona  # noqa: E402, F401
import db.models.topic  # noqa: E402, F401
import db.models.content  # noqa: E402, F401


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
