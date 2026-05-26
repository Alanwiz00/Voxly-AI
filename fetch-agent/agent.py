"""VoxlyAI Fetch.ai uAgent — receives content generation requests via Agentverse mailbox."""
import os
import httpx
from uagents import Agent, Context, Model, Protocol
from dotenv import load_dotenv

load_dotenv()

VOXLY_API_URL = os.environ.get("VOXLY_API_URL", "http://localhost:8000")
VOXLY_API_KEY = os.environ["VOXLY_API_KEY"]
AGENT_SEED = os.environ["AGENT_SEED"]
AGENT_NAME = os.environ.get("AGENT_NAME", "voxlyai-content-generator")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8002"))
AGENT_INSPECTOR = os.environ.get("AGENT_INSPECTOR", "true").lower() == "true"

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    mailbox=True,
    enable_agent_inspector=AGENT_INSPECTOR,
    description=(
        "AI-powered social media content generator. "
        "Generates posts, threads, and articles for Twitter, Instagram, Facebook, and Telegram."
    ),
)

# ---------------------------------------------------------------------------
# HTTP client — lazy, shared for the process lifetime
# ---------------------------------------------------------------------------

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=VOXLY_API_URL,
            headers={"Authorization": f"Bearer {VOXLY_API_KEY}"},
            timeout=90.0,
        )
    return _http


# ---------------------------------------------------------------------------
# Message models
# ---------------------------------------------------------------------------

class GenerateRequest(Model):
    """Request content generation from VoxlyAI.

    platform:     twitter | instagram | facebook | telegram
    content_type: idea | long_form | thread | article
    """
    topic: str
    platform: str
    content_type: str
    idea_count: int = 4
    persona_id: int | None = None


class GenerateResponse(Model):
    results: list[str]
    error: str | None = None


class ListTopicsRequest(Model):
    """Request the list of saved VoxlyAI topics."""
    pass


class ListTopicsResponse(Model):
    topics: list[dict]
    error: str | None = None


class ListPersonasRequest(Model):
    """Request the list of configured VoxlyAI personas."""
    pass


class ListPersonasResponse(Model):
    personas: list[dict]
    error: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

voxlyai = Protocol(name="VoxlyAI", version="1.0.0")


@voxlyai.on_message(model=GenerateRequest, replies=GenerateResponse)
async def handle_generate(ctx: Context, sender: str, msg: GenerateRequest):
    ctx.logger.info(f"GenerateRequest from {sender[:20]}… | {msg.topic} / {msg.platform} / {msg.content_type}")
    try:
        payload: dict = {
            "topic_name": msg.topic,
            "platform": msg.platform,
            "content_type": msg.content_type,
            "idea_count": msg.idea_count,
        }
        if msg.persona_id is not None:
            payload["persona_id"] = msg.persona_id

        resp = await _client().post("/generate/", json=payload)
        resp.raise_for_status()
        raw = resp.json().get("results", [])
        results = [
            f"{r.get('title') or 'Untitled'}\n\n{r['content']}" for r in raw
        ]
        await ctx.send(sender, GenerateResponse(results=results))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        ctx.logger.error(f"API error: {detail}")
        await ctx.send(sender, GenerateResponse(results=[], error=detail))
    except Exception as e:
        ctx.logger.error(f"Generate failed: {e}")
        await ctx.send(sender, GenerateResponse(results=[], error=str(e)))


@voxlyai.on_message(model=ListTopicsRequest, replies=ListTopicsResponse)
async def handle_list_topics(ctx: Context, sender: str, msg: ListTopicsRequest):
    ctx.logger.info(f"ListTopicsRequest from {sender[:20]}…")
    try:
        resp = await _client().get("/topics/")
        resp.raise_for_status()
        await ctx.send(sender, ListTopicsResponse(topics=resp.json()))
    except Exception as e:
        ctx.logger.error(f"ListTopics failed: {e}")
        await ctx.send(sender, ListTopicsResponse(topics=[], error=str(e)))


@voxlyai.on_message(model=ListPersonasRequest, replies=ListPersonasResponse)
async def handle_list_personas(ctx: Context, sender: str, msg: ListPersonasRequest):
    ctx.logger.info(f"ListPersonasRequest from {sender[:20]}…")
    try:
        resp = await _client().get("/persona/")
        resp.raise_for_status()
        await ctx.send(sender, ListPersonasResponse(personas=resp.json()))
    except Exception as e:
        ctx.logger.error(f"ListPersonas failed: {e}")
        await ctx.send(sender, ListPersonasResponse(personas=[], error=str(e)))


agent.include(voxlyai, publish_manifest=True)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("=" * 60)
    ctx.logger.info("VoxlyAI Fetch.ai agent started")
    ctx.logger.info(f"Agent name:    {AGENT_NAME}")
    ctx.logger.info(f"Agent address: {agent.address}")
    ctx.logger.info("Share the address above with other agents on Agentverse")
    ctx.logger.info("=" * 60)


if __name__ == "__main__":
    agent.run()
