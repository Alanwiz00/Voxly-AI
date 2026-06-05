from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str
    DATABASE_URL: str
    QDRANT_URL: str
    QDRANT_API_KEY: str
    OPENAI_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    NEXTAUTH_SECRET: str

    # Comma-separated allowed CORS origins — add your production frontend URL here
    # e.g. ALLOWED_ORIGINS=https://app.yourdomain.com,http://localhost:3000
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Comma-separated list of emails that are pre-authorized on first boot
    # e.g. ADMIN_EMAILS=you@gmail.com,colleague@gmail.com
    ADMIN_EMAILS: str = ""

    # Crawl schedule — every N hours
    CRAWL_INTERVAL_HOURS: int = 6

    # Qdrant collection names
    PERSONA_COLLECTION: str = "user_personas"
    SENTIMENT_COLLECTION: str = "topic_sentiment"

    # OpenAI models
    OPENAI_GENERATION_MODEL: str = "gpt-4o"
    OPENAI_FAST_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIM: int = 1536


settings = Settings()
