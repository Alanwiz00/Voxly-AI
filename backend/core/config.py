from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Defaults to production so a deploy that forgets to set it doesn't echo SQL
    # or return exception details; dev compose and .env.example set "development".
    APP_ENV: str = "production"
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

    # Optional: NewsAPI key for authoritative news crawling (https://newsapi.org)
    NEWS_API_KEY: str = ""

    # Crawl schedule — every N hours (12h default; override via env var)
    CRAWL_INTERVAL_HOURS: int = 12

    # Batch dispatch: topics per batch and seconds between batches
    CRAWL_BATCH_SIZE: int = 5
    CRAWL_BATCH_GAP_SECS: int = 600   # 10 minutes between batches

    # Qdrant collection names
    PERSONA_COLLECTION: str = "user_personas"
    SENTIMENT_COLLECTION: str = "topic_sentiment"

    # OpenAI — vision (extract_from_image), embeddings, and last-resort
    # text generation when both Groq and Gemini fail
    OPENAI_GENERATION_MODEL: str = "gpt-4o"   # vision fallback only
    OPENAI_FAST_MODEL: str = "gpt-4o-mini"
    OPENAI_SENTIMENT_MODEL: str = "gpt-4o-mini"
    OPENAI_TEXT_MODEL: str = "gpt-4o-mini"   # text generation fallback (after Groq, Gemini)
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIM: int = 1536

    # Groq — primary text generation
    GROQ_API_KEY: str = ""
    GROQ_GENERATION_MODEL: str = "llama-3.1-8b-instant"

    # Gemini — fallback text generation
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Per-user token budget (0 = unlimited). Override per-user in the DB.
    DEFAULT_MONTHLY_TOKEN_LIMIT: int = 100_000

    # Listening & outreach on X. Prices are X pay-per-use rates (USD); X says they can
    # change, so keep them in sync with the developer console.
    X_BEARER_TOKEN: str = ""
    X_API_BASE_URL: str = "https://api.x.com"
    X_ACCOUNT_USER_ID: str = ""  # the account that posts replies; its mentions are read for replies
    X_PRICE_POST_READ: float = 0.005
    X_PRICE_USER_READ: float = 0.010
    X_PRICE_COUNTS_REQUEST: float = 0.005
    LISTENING_MONTHLY_BUDGET_USD: float = 15.0  # hard stop across all campaigns
    X_QUERY_MAX_CHARS: int = 512  # X recent-search limit on self-serve access (enterprise: 4096)

    # BetEye: proof for drafts, and signed signup events back to Voxly
    BETEYE_API_URL: str = ""
    BETEYE_OUTREACH_KEY: str = ""
    LISTENING_WEBHOOK_SECRET: str = ""


settings = Settings()
