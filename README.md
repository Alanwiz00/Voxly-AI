# VoxlyAI

**Your voice, amplified.**

VoxlyAI crawls the web for topic sentiment, learns how you write from your edit history, and generates platform-native content that sounds like you — across Twitter/X, Instagram, Facebook, and Telegram.

## What it does

- **Crawler** — Track topics and pull fresh sentiment from the web every 6 hours or on demand. Every crawl auto-generates reusable short posts and long-form content ready to adapt.
- **Platform adaptation** — One click rewrites any post natively for the target platform: thread, caption, channel post, or story format.
- **Persona & style learning** — Set your niche, tone, and voice once. VoxlyAI then watches how you edit and builds a style profile that sharpens every generation over time.
- **Multiple sources** — Generate from a saved topic, pasted text, a URL, or an uploaded PDF/DOCX.
- **Re-edit & version history** — Every piece is versioned. Give a plain-English instruction and the AI rewrites without drifting from your voice.
- **Access control** — Email allowlist with Google OAuth. Unauthorized accounts are blocked before a session is created.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, Tailwind CSS, shadcn/ui, Auth.js v5 (Google OAuth) |
| Backend | FastAPI, Python 3.12, async SQLAlchemy |
| LLM | OpenAI gpt-4o (generation), gpt-4o-mini (sentiment + style synthesis) |
| Vector DB | Qdrant Cloud |
| SQL DB | PostgreSQL via Supabase |
| Task queue | Celery + Redis, Celery Beat |
| Crawling | Firecrawl + Tavily |

## Quick start (local)

**Prerequisites:** Docker + Docker Compose, and accounts for OpenAI, Supabase, Qdrant Cloud, Firecrawl, Tavily, and Google Cloud OAuth.

```bash
git clone https://github.com/Alanwiz00/Voxly-AI
cd Voxly-AI

cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Fill in both .env files with your credentials

# Generate a shared secret — paste the same value into NEXTAUTH_SECRET in both .env files
openssl rand -base64 32

docker compose up -d
```

| Service | URL |
|---|---|
| App | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Celery monitor | http://localhost:5555 |

## Environment variables

### `backend/.env`

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random secret, min 32 chars |
| `DATABASE_URL` | Supabase connection string (`postgresql+asyncpg://...`) |
| `QDRANT_URL` | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `FIRECRAWL_API_KEY` | Firecrawl API key |
| `TAVILY_API_KEY` | Tavily API key |
| `NEXTAUTH_SECRET` | Must match the frontend value exactly |
| `ADMIN_EMAILS` | Comma-separated emails authorized on first boot |
| `ALLOWED_ORIGINS` | Comma-separated allowed frontend URLs |

### `frontend/.env`

| Variable | Description |
|---|---|
| `NEXTAUTH_URL` | Full public URL of the frontend |
| `NEXTAUTH_SECRET` | Must match the backend value exactly |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `NEXT_PUBLIC_API_URL` | Public URL of the backend API |

## Google OAuth setup

1. [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → Create OAuth 2.0 Client
2. Add authorized redirect URI: `https://app.yourdomain.com/api/auth/callback/google`
3. Copy the client ID and secret into `frontend/.env`

## Deployment (Dokploy)

1. Push the repo to GitHub
2. On your VPS: `curl -sSL https://dokploy.com/install.sh | sh`
3. In Dokploy: **New Project → Compose** → connect your repo, set compose file to `docker-compose.prod.yml`
4. Add all env vars in the **Environment** tab
5. In **Domains**, map `app.yourdomain.com → port 3000` and `api.yourdomain.com → port 8000`
6. Deploy — SSL is provisioned automatically via Let's Encrypt

## Project structure

```
voxlyai/
├── backend/
│   ├── api/routes/        # FastAPI route handlers
│   ├── db/
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── postgres.py    # DB engine and session
│   │   └── qdrant.py      # Vector DB client
│   ├── services/          # generator, crawler, sentiment, persona, style synthesis
│   ├── workers/           # Celery tasks — crawl + auto-generation
│   └── main.py
├── frontend/
│   ├── app/(dashboard)/   # Generate, Crawler, History, Settings pages
│   ├── components/        # Sidebar and shared UI
│   └── lib/               # API client, auth config, utilities
├── docker-compose.yml      # Development
└── docker-compose.prod.yml # Production
```

# git AI image generator prompt (Midjourney / Ideogram / DALL-E):
Minimal flat logo icon for "VoxlyAI", an AI voice and content generation brand.
Design: five vertical pill-shaped bars arranged in a symmetric arch — shortest
on the outside, tallest in the center — representing a sound waveform or voice
signal. Rendered in crisp white on a deep indigo-to-violet gradient rounded
square background (#818cf8 → #4f46e5). Ultra-clean, no text, no shadows,
no gradients on the bars. Style: modern SaaS app icon, Apple-level minimalism.
Output as a 1:1 square, suitable for favicon and app icon use.

