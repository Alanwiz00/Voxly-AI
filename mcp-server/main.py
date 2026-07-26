"""VoxlyAI MCP Server — MCP JSON-RPC over plain HTTP (no SSE / streaming required)."""
import os
import httpx
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
import uvicorn

load_dotenv()

VOXLY_API_URL = os.environ.get("VOXLY_API_URL", "http://localhost:8000")
VOXLY_API_KEY = os.environ["VOXLY_API_KEY"]
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))

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
# Tool implementations
# ---------------------------------------------------------------------------

async def _generate_content(
    topic: str,
    platform: str,
    content_type: str,
    idea_count: int = 4,
    persona_id: int | None = None,
) -> str:
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
        f"**{r.get('title') or 'Untitled'}**\n\n{r['content']}" for r in results
    )


async def _list_topics() -> str:
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


async def _list_personas() -> str:
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


async def _get_recent_content(
    limit: int = 10,
    platform: str | None = None,
    content_type: str | None = None,
) -> str:
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
# MCP tool manifest
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "generate_content",
        "description": (
            "Generate AI-powered social media content for a topic using VoxlyAI.\n\n"
            "platform:     twitter | instagram | facebook | telegram\n"
            "content_type: idea | long_form | thread | article\n"
            "idea_count:   number of ideas to generate (applies when content_type=idea)\n"
            "persona_id:   optional persona to use; omit to let VoxlyAI auto-select"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic":        {"type": "string",  "description": "The topic or subject to generate content about"},
                "platform":     {"type": "string",  "description": "twitter | instagram | facebook | telegram"},
                "content_type": {"type": "string",  "description": "idea | long_form | thread | article"},
                "idea_count":   {"type": "integer", "description": "Number of idea variants (default: 4)", "default": 4},
                "persona_id":   {"type": "integer", "description": "Persona ID to use (optional)"},
            },
            "required": ["topic", "platform", "content_type"],
        },
    },
    {
        "name": "list_topics",
        "description": "List all saved topics in VoxlyAI (recurring subjects used for content generation).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_personas",
        "description": "List all writing personas configured in VoxlyAI (each has a distinct tone and brand voice).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_content",
        "description": "Retrieve recently generated content from VoxlyAI history.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit":        {"type": "integer", "description": "Max items to return (default: 10, capped at 50)", "default": 10},
                "platform":     {"type": "string",  "description": "Filter by platform (optional): twitter | instagram | facebook | telegram"},
                "content_type": {"type": "string",  "description": "Filter by type (optional): idea | long_form | thread | article"},
            },
            "required": [],
        },
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# ---------------------------------------------------------------------------
# MCP JSON-RPC handler
# ---------------------------------------------------------------------------

async def handle_mcp(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Accept",
            },
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params") or {}

    # --- initialize ---
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "VoxlyAI", "version": "1.0.0"},
            },
        })

    # --- tools/list ---
    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        })

    # --- tools/call ---
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}

        if name not in TOOL_MAP:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            })

        try:
            if name == "generate_content":
                text = await _generate_content(
                    topic=args.get("topic", ""),
                    platform=args.get("platform", "twitter"),
                    content_type=args.get("content_type", "idea"),
                    idea_count=int(args.get("idea_count", 4)),
                    persona_id=args.get("persona_id"),
                )
            elif name == "list_topics":
                text = await _list_topics()
            elif name == "list_personas":
                text = await _list_personas()
            elif name == "get_recent_content":
                text = await _get_recent_content(
                    limit=int(args.get("limit", 10)),
                    platform=args.get("platform"),
                    content_type=args.get("content_type"),
                )
            else:
                text = "Tool not implemented."
        except Exception as exc:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            },
        })

    # --- notifications (fire-and-forget, no response body needed) ---
    if method.startswith("notifications/"):
        return Response(status_code=202)

    # --- unknown method ---
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    })


async def handle_health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "VoxlyAI MCP Server"})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Starlette(
    routes=[
        Route("/mcp",    handle_mcp,    methods=["POST", "OPTIONS"]),
        Route("/health", handle_health, methods=["GET"]),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT, log_level="info")
