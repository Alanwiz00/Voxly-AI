# ContentAI — AI Social Media Content Generator

An AI-powered content platform that crawls the web for topic sentiment, auto-generates reusable posts, and adapts them natively for Twitter/X, Instagram, Facebook, and Telegram.

## Features

- **Crawler** — Add topics and crawl the web every 6 hours (or on demand). Sentiment is analysed and stored as vector embeddings.
- **Auto-generation** — After every crawl, 3 short post ideas + 1 long-form post are generated automatically from fresh sentiment data.
- **Platform adaptation** — One click converts any reusable post into a platform-native format (thread, caption, channel post, etc.).
- **Manual generation** — Generate content from a topic, pasted text, URL, or uploaded PDF/DOCX.
- **Persona system** — Set your niche, tone, brand voice, and sample content. The AI matches your style on every generation.
- **Style learning** — The AI analyses your re-edit history and builds a style profile that improves generation over time. Auto-updates every 5 re-edits.
- **Multi-account** — Email allowlist controls who can sign in. Pre-authorize accounts via `ADMIN_EMAILS` on first boot.
- **Content history** — Full re-edit and versioning history for every generated piece.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, Tailwind CSS, shadcn/ui, Auth.js v5 (Google OAuth) |
| Backend | FastAPI, Python 3.12, SQLAlchemy (async), asyncpg |
| LLM | OpenAI gpt-4o (generation), gpt-4o-mini (sentiment + style) |
| Vector DB | Qdrant Cloud |
| SQL DB | PostgreSQL (Supabase) |
| Task queue | Celery + Redis, Celery Beat |
| Crawling | Firecrawl + Tavily |

## Quick Start (local)

### Prerequisites

- Docker + Docker Compose
- Accounts: OpenAI, Supabase, Qdrant Cloud, Firecrawl, Tavily, Google Cloud (OAuth)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/content-generator.git
cd content-generator
```

Copy and fill in both env files:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 2. Generate secrets

```bash
# Run once, paste the same value into NEXTAUTH_SECRET in both .env files
openssl rand -base64 32
```

### 3. Start

```bash
docker compose up -d
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Flower (Celery) | http://localhost:5555 |

## Environment Variables

### `backend/.env`

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random secret (min 32 chars) |
| `DATABASE_URL` | Supabase PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `QDRANT_URL` | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `FIRECRAWL_API_KEY` | Firecrawl API key |
| `TAVILY_API_KEY` | Tavily API key |
| `NEXTAUTH_SECRET` | Must match the frontend value exactly |
| `ADMIN_EMAILS` | Comma-separated emails pre-authorized on first boot |
| `ALLOWED_ORIGINS` | Comma-separated allowed frontend URLs (e.g. `https://app.yourdomain.com`) |

### `frontend/.env`

| Variable | Description |
|---|---|
| `NEXTAUTH_URL` | Full URL of the frontend (e.g. `https://app.yourdomain.com`) |
| `NEXTAUTH_SECRET` | Must match the backend value exactly |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `NEXT_PUBLIC_API_URL` | Public URL of the backend API |

## Google OAuth Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URI: `https://app.yourdomain.com/api/auth/callback/google`
4. Copy the client ID and secret into `frontend/.env`

## Deployment (Dokploy)

1. Push the repo to GitHub
2. On your VPS: `curl -sSL https://dokploy.com/install.sh | sh`
3. In Dokploy: **New Project** → **Compose** service → point to your repo, use `docker-compose.prod.yml`
4. Set all environment variables in the Dokploy **Environment** tab
5. In **Domains**, add `app.yourdomain.com → port 3000` and `api.yourdomain.com → port 8000`
6. Deploy — Dokploy handles SSL via Let's Encrypt automatically

## Project Structure

```
content-generator/
├── backend/
│   ├── api/routes/        # FastAPI route handlers
│   ├── db/
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── postgres.py    # DB engine and session
│   │   └── qdrant.py      # Vector DB client
│   ├── services/          # Business logic (generator, crawler, sentiment, persona)
│   ├── workers/           # Celery tasks (crawl + auto-generation)
│   └── main.py
├── frontend/
│   ├── app/(dashboard)/   # Dashboard pages (generate, crawler, history, settings)
│   ├── components/        # Shared UI components
│   └── lib/               # API client, auth, utilities
├── docker-compose.yml      # Development
└── docker-compose.prod.yml # Production
```
