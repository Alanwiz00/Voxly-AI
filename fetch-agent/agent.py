"""VoxlyAI Fetch.ai uAgent — receives content generation requests via Agentverse."""
import os
import httpx
from datetime import datetime, timezone
from uuid import uuid4
from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from dotenv import load_dotenv

load_dotenv()

VOXLY_API_URL = os.environ.get("VOXLY_API_URL", "http://localhost:8000")
VOXLY_API_KEY = os.environ["VOXLY_API_KEY"]
AGENT_SEED = os.environ["AGENT_SEED"]
AGENT_NAME = os.environ.get("AGENT_NAME", "voxlyai-content-generator")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8002"))
AGENT_INSPECTOR = os.environ.get("AGENT_INSPECTOR", "true").lower() == "true"
AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT", "")

agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=AGENT_ENDPOINT if AGENT_ENDPOINT else None,
    mailbox=not bool(AGENT_ENDPOINT),
    enable_agent_inspector=AGENT_INSPECTOR,
    description=(
        "Generate social media content, posts, tweets, threads, and articles using AI. "
        "Create engaging content for Twitter, Instagram, Facebook, and Telegram. "
        "Supports multiple content formats: ideas, long-form posts, tweet threads, and articles. "
        "Uses your brand voice and writing style to produce on-brand content at scale. "
        "Ideal for content creators, marketers, and brands who need AI-powered copywriting."
    ),
    metadata={
        "tags": [
            "content-generation", "social-media", "copywriting",
            "twitter", "instagram", "facebook", "telegram",
            "ai-writing", "marketing", "content-creation",
            "threads", "articles", "brand-voice",
        ],
        "category": "content-generation",
        "author": "VoxlyAI",
        "version": "1.0.0",
    },
)

# ---------------------------------------------------------------------------
# HTTP client
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
# Intent parser — extracts platform / content_type / topic from plain text
# ---------------------------------------------------------------------------

def _parse_intent(text: str) -> tuple[str, str, str]:
    t = text.lower()

    if any(w in t for w in ["twitter", "tweet", "x.com"]):
        platform = "twitter"
    elif any(w in t for w in ["instagram", "insta", " ig "]):
        platform = "instagram"
    elif any(w in t for w in ["facebook", " fb "]):
        platform = "facebook"
    elif "telegram" in t:
        platform = "telegram"
    else:
        platform = "twitter"

    if "thread" in t:
        content_type = "thread"
    elif any(w in t for w in ["article", "blog", "essay"]):
        content_type = "article"
    elif any(w in t for w in ["long-form", "long form", "longform"]):
        content_type = "long_form"
    else:
        content_type = "idea"

    filler = [
        "write me", "generate me", "create me", "give me", "make me",
        "write", "generate", "create", "produce", "draft", "make",
        "a twitter", "an instagram", "a facebook", "a telegram",
        "twitter", "instagram", "facebook", "telegram", "tweet",
        "thread", "post", "article", "ideas", "idea", "content", "caption",
        "about", "regarding", "related to", "please", "can you",
    ]
    topic = text
    for w in sorted(filler, key=len, reverse=True):
        topic = topic.lower().replace(w, " ")
    topic = " ".join(topic.split()).strip()

    return platform, content_type, topic or text


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# AgentChatProtocol — handles DeltaV / Agentverse chat interface
# ---------------------------------------------------------------------------

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge immediately so the sender knows the message was received
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=_now(),
        acknowledged_msg_id=msg.msg_id,
        metadata=None,
    ))

    # Extract plain text from the content array
    text = " ".join(
        item.text for item in msg.content
        if hasattr(item, "type") and item.type == "text"
    ).strip()

    ctx.logger.info(f"Chat message from {sender[:20]}…: {text[:80]}")

    if not text:
        await ctx.send(sender, ChatMessage(
            timestamp=_now(),
            msg_id=str(uuid4()),
            content=[TextContent(type="text", text=(
                "Hi! Tell me what content you'd like to generate.\n\n"
                "Example: \"Write a Twitter thread about AI in healthcare\""
            ))],
        ))
        return

    platform, content_type, topic = _parse_intent(text)
    ctx.logger.info(f"Parsed → platform={platform} type={content_type} topic={topic}")

    try:
        resp = await _client().post("/generate/", json={
            "topic_name": topic,
            "platform": platform,
            "content_type": content_type,
            "idea_count": 4,
        })
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            reply = "No content was generated. Please try a more specific topic."
        elif len(results) == 1:
            r = results[0]
            title = r.get("title") or ""
            body = r["content"].replace("\n\n---\n\n", "\n\n")
            reply = f"**{title}**\n\n{body}" if title else body
        else:
            parts = []
            for i, r in enumerate(results, 1):
                title = r.get("title") or f"Option {i}"
                body = r["content"].replace("\n\n---\n\n", "\n\n")
                parts.append(f"**Option {i}: {title}**\n\n{body}")
            reply = "\n\n---\n\n".join(parts)

    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        ctx.logger.error(f"API error: {detail}")
        reply = f"Sorry, the content generator returned an error: {detail}"
    except Exception as e:
        ctx.logger.error(f"Chat generate failed: {e}")
        reply = f"Sorry, something went wrong: {e}"

    await ctx.send(sender, ChatMessage(
        timestamp=_now(),
        msg_id=str(uuid4()),
        content=[TextContent(type="text", text=reply)],
    ))


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Ack from {sender[:20]}… for msg {msg.acknowledged_msg_id}")


agent.include(chat_proto, publish_manifest=True)


# ---------------------------------------------------------------------------
# VoxlyAI typed protocol — for agent-to-agent use
# ---------------------------------------------------------------------------

class GenerateRequest(Model):
    """Generate AI-powered social media content.

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
    """List all saved VoxlyAI topics."""
    pass


class ListTopicsResponse(Model):
    topics: list[dict]
    error: str | None = None


class ListPersonasRequest(Model):
    """List all VoxlyAI writing personas."""
    pass


class ListPersonasResponse(Model):
    personas: list[dict]
    error: str | None = None


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
        results = [f"{r.get('title') or 'Untitled'}\n\n{r['content']}" for r in raw]
        await ctx.send(sender, GenerateResponse(results=results))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        await ctx.send(sender, GenerateResponse(results=[], error=detail))
    except Exception as e:
        await ctx.send(sender, GenerateResponse(results=[], error=str(e)))


@voxlyai.on_message(model=ListTopicsRequest, replies=ListTopicsResponse)
async def handle_list_topics(ctx: Context, sender: str, msg: ListTopicsRequest):
    try:
        resp = await _client().get("/topics/")
        resp.raise_for_status()
        await ctx.send(sender, ListTopicsResponse(topics=resp.json()))
    except Exception as e:
        await ctx.send(sender, ListTopicsResponse(topics=[], error=str(e)))


@voxlyai.on_message(model=ListPersonasRequest, replies=ListPersonasResponse)
async def handle_list_personas(ctx: Context, sender: str, msg: ListPersonasRequest):
    try:
        resp = await _client().get("/persona/")
        resp.raise_for_status()
        await ctx.send(sender, ListPersonasResponse(personas=resp.json()))
    except Exception as e:
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
    ctx.logger.info("=" * 60)

    agentverse_key = os.environ.get("AGENTVERSE_KEY", "")
    if agentverse_key and AGENT_ENDPOINT:
        try:
            from uagents_core.utils.registration import (
                register_chat_agent,
                RegistrationRequestCredentials,
            )
            endpoint = AGENT_ENDPOINT if AGENT_ENDPOINT.startswith("https://") else f"https://{AGENT_ENDPOINT}"
            register_chat_agent(
                "Voxly AI",
                endpoint,
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=agentverse_key,
                    agent_seed_phrase=AGENT_SEED,
                ),
            )
            ctx.logger.info("Registered with Agentverse DeltaV chat")
        except Exception as e:
            ctx.logger.error(f"Agentverse registration failed: {e}")
    else:
        ctx.logger.warning("AGENTVERSE_KEY or AGENT_ENDPOINT not set — skipping DeltaV registration")


@agent.on_interval(period=30.0)
async def heartbeat(ctx: Context):
    ctx.logger.debug("Heartbeat — listening for messages")


if __name__ == "__main__":
    agent.run()
