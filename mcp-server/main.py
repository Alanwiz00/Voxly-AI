"""VoxlyAI MCP Server — exposes content generation as MCP tools over SSE transport."""
import os
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

VOXLY_API_URL = os.environ.get("VOXLY_API_URL", "http://localhost:8000")
VOXLY_API_KEY = os.environ["VOXLY_API_KEY"]
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))

mcp = FastMCP("VoxlyAI", host=MCP_HOST, port=MCP_PORT)

# Lazy-initialised shared client — one connection pool for the process lifetime
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
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_content(
    topic: str,
    platform: str,
    content_type: str,
    idea_count: int = 4,
    persona_id: int | None = None,
) -> str:
    """Generate AI-powered social media content for a topic using VoxlyAI.

    platform:     twitter | instagram | facebook | telegram
    content_type: idea | long_form | thread | article
    idea_count:   number of ideas to generate (only applies when content_type=idea)
    persona_id:   optional persona to use; omit to let VoxlyAI auto-select the best match
    """
    payload: dict = {
        "topic_name": topic,
        "platform": platform,
        "content_type": content_type,
        "idea_count": idea_count,
    }
    if persona_id is not None:
        payload["persona_id"] = persona_id

    try:
        resp = await _client().post("/generate/", json=payload)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e)) if e.response.content else str(e)
        return f"Error from VoxlyAI: {detail}"

    results = resp.json().get("results", [])
    if not results:
        return "No content generated."

    return "\n\n---\n\n".join(
        f"**{r.get('title') or 'Untitled'}**\n\n{r['content']}"
        for r in results
    )


@mcp.tool()
async def list_topics() -> str:
    """List all saved topics in VoxlyAI.

    Topics are recurring subjects used for crawling and content generation.
    Returns the topic ID (needed to pass topic_id to generate_content) plus status.
    """
    try:
        resp = await _client().get("/topics/")
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code}"

    topics = resp.json()
    if not topics:
        return "No topics saved yet."

    lines = []
    for t in topics:
        status = "active" if t["is_active"] else "paused"
        crawled = f" — last crawled {t['last_crawled_at'][:10]}" if t.get("last_crawled_at") else ""
        lines.append(f"[{t['id']}] {t['name']} ({status}){crawled}")
    return "\n".join(lines)


@mcp.tool()
async def list_personas() -> str:
    """List all writing personas configured in VoxlyAI.

    Each persona has a distinct tone, niche, and brand voice.
    Returns the persona ID needed to explicitly select one in generate_content.
    """
    try:
        resp = await _client().get("/persona/")
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code}"

    personas = resp.json()
    if not personas:
        return "No personas configured."

    lines = []
    for p in personas:
        tag = " [default]" if p.get("is_default") else ""
        detail = " | ".join(filter(None, [p.get("niche"), p.get("tone"), p.get("target_audience")]))
        suffix = f" — {detail}" if detail else ""
        lines.append(f"[{p['id']}] {p['name']}{tag}{suffix}")
    return "\n".join(lines)


@mcp.tool()
async def get_recent_content(
    limit: int = 10,
    platform: str | None = None,
    content_type: str | None = None,
) -> str:
    """Retrieve recently generated content from VoxlyAI history.

    platform (optional):     twitter | instagram | facebook | telegram
    content_type (optional): idea | long_form | thread | article
    limit:                   max items to return (default 10, capped at 50)
    """
    params: dict = {"limit": min(limit, 50)}
    if platform:
        params["platform"] = platform
    if content_type:
        params["content_type"] = content_type

    try:
        resp = await _client().get("/content/", params=params)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Error: {e.response.status_code}"

    items = resp.json()
    if not items:
        return "No content found."

    lines = []
    for item in items:
        preview = (item.get("title") or item["content"][:80]).replace("\n", " ")
        lines.append(f"[{item['id']}] {item['platform']} / {item['content_type']} — {preview}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="sse")
