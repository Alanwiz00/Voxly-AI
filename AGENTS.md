# VoxlyAI — Agent Integration Guide

VoxlyAI exposes its content generation capabilities to external AI agents through two protocols:

| Service | Protocol | Port | Best for |
|---|---|---|---|
| `mcp-server` | Model Context Protocol (SSE) | 8001 | Claude Desktop, Claude Code, any MCP-compatible host |
| `fetch-agent` | Fetch.ai uAgent (Agentverse) | 8002 (inspector) | Agent-to-agent marketplace, automated pipelines |

Both services authenticate to the VoxlyAI backend with a `vlx-` API key and are fully isolated from the main application.

---

## Prerequisites

1. VoxlyAI is running and reachable (backend on port 8000)
2. You have an admin account — only admins can create API keys
3. Sign in, go to **Settings → API Keys**, and create one key per service

> Create a separate key for each service so you can revoke them independently.

---

## MCP Server

### What it exposes

| Tool | Description |
|---|---|
| `generate_content` | Generate posts, threads, or articles for a topic and platform |
| `list_topics` | List saved topics with their IDs |
| `list_personas` | List writing personas with their IDs |
| `get_recent_content` | Browse recent content history |

### Setup

**1. Create the API key**

Sign in as admin → **Settings → API Keys** → Create key named `"MCP Server"` → copy the `vlx-…` value.

**2. Set env vars**

Add to your root `.env`:

```env
VOXLY_MCP_API_KEY=vlx-your-key-here
```

**3. Start the service**

```bash
# Alongside the full stack
docker compose up -d mcp-server

# Or standalone (requires backend already running)
docker compose up mcp-server
```

The server will be available at `http://localhost:8001/sse`.

**4. Verify**

```bash
curl -N http://localhost:8001/sse
# Should open an SSE stream — Ctrl+C to close
```

---

### Connect to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "voxlyai": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8001/sse"
      ]
    }
  }
}
```

Restart Claude Desktop. You will see VoxlyAI tools listed under the 🔌 icon.

> **Production:** Replace `http://localhost:8001/sse` with your public URL, e.g. `https://mcp.yourdomain.com/sse`. The `mcp-server` is on `dokploy-network` in prod so it can be routed by your reverse proxy.

---

### Connect to Claude Code (CLI)

```bash
claude mcp add voxlyai --transport sse http://localhost:8001/sse
```

Then in any Claude Code session:

```
/mcp
# Lists connected servers — voxlyai should appear

Generate a Twitter thread about "AI in healthcare" using VoxlyAI
```

---

### Example tool call (direct)

Any MCP-compatible client can invoke tools. Example payload for `generate_content`:

```json
{
  "topic": "Web3 and creator economy",
  "platform": "twitter",
  "content_type": "thread",
  "idea_count": 4
}
```

---

## Fetch.ai uAgent

### What it exposes

The agent registers on [Agentverse](https://agentverse.ai) and listens for messages via the `VoxlyAI` protocol. Other agents send typed messages and receive typed responses — no HTTP required.

| Message | Reply | Description |
|---|---|---|
| `GenerateRequest` | `GenerateResponse` | Generate content for a topic |
| `ListTopicsRequest` | `ListTopicsResponse` | Get saved topic list |
| `ListPersonasRequest` | `ListPersonasResponse` | Get persona list |

### Setup

**1. Create the API key**

Sign in as admin → **Settings → API Keys** → Create key named `"Fetch Agent"` → copy the `vlx-…` value.

**2. Generate a stable agent seed**

The seed is the agent's permanent identity — the same seed always produces the same address. **Back it up safely.**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Example output: a3f8c2d1e4b5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1
```

**3. Set env vars**

Add to your root `.env`:

```env
VOXLY_FETCH_API_KEY=vlx-your-key-here
FETCH_AGENT_SEED=your-64-char-hex-seed-here
```

**4. Start the service**

```bash
docker compose up -d fetch-agent
```

**5. Get the agent address**

```bash
docker compose logs fetch-agent | grep "Agent address"
# ============================================================
# VoxlyAI Fetch.ai agent started
# Agent name:    voxlyai-content-generator
# Agent address: agent1q...
# ============================================================
```

Copy the `agent1q…` address — you will need it for Agentverse registration and for other agents to reach you.

---

### Register on Agentverse

1. Go to [agentverse.ai](https://agentverse.ai) and sign in
2. Click **New Agent** → **Connect local agent**
3. Paste the `agent1q…` address from the logs
4. Give it a name (e.g. `VoxlyAI Content Generator`) and a description
5. Click **Connect** — the agent's mailbox is now active

Once connected, the agent is discoverable in the Agentverse marketplace and other agents can message it without a direct network connection to your server.

---

### Interact from another agent

Any uAgent can send a `GenerateRequest` by importing the same model schema. Example:

```python
from uagents import Agent, Context, Model

VOXLYAI_ADDRESS = "agent1q..."  # paste the address from logs

class GenerateRequest(Model):
    topic: str
    platform: str       # twitter | instagram | facebook | telegram
    content_type: str   # idea | long_form | thread | article
    idea_count: int = 4
    persona_id: int | None = None

class GenerateResponse(Model):
    results: list[str]
    error: str | None = None

caller = Agent(name="my-agent", seed="my-agent-seed")

@caller.on_event("startup")
async def send_request(ctx: Context):
    await ctx.send(
        VOXLYAI_ADDRESS,
        GenerateRequest(
            topic="Decentralized AI",
            platform="twitter",
            content_type="thread",
        ),
    )

@caller.on_message(model=GenerateResponse)
async def handle_response(ctx: Context, sender: str, msg: GenerateResponse):
    if msg.error:
        ctx.logger.error(f"Error: {msg.error}")
    else:
        for item in msg.results:
            print(item)
        print("---")

caller.run()
```

---

### Agent inspector (dev only)

When `AGENT_INSPECTOR=true` (default in dev), a local web UI runs at `http://localhost:8002`. It shows:

- The agent's address and identity
- Message history
- Protocol manifest
- A button to set up the Agentverse mailbox connection

Set `AGENT_INSPECTOR=false` in production (already done in `docker-compose.prod.yml`).

---

## Running both services together

```bash
# Start everything
docker compose up -d

# Start only the agent services (backend must already be healthy)
docker compose up -d mcp-server fetch-agent

# View logs
docker compose logs -f mcp-server
docker compose logs -f fetch-agent

# Rebuild after code changes
docker compose build mcp-server fetch-agent
docker compose up -d mcp-server fetch-agent
```

---

## Environment variable reference

All variables below go in the root `.env` file (same file used by docker compose).

| Variable | Required | Description |
|---|---|---|
| `VOXLY_MCP_API_KEY` | MCP server | `vlx-` key from VoxlyAI Settings |
| `VOXLY_FETCH_API_KEY` | Fetch agent | `vlx-` key from VoxlyAI Settings |
| `FETCH_AGENT_SEED` | Fetch agent | 64-char hex seed — determines agent address |

---

## Production notes

- **MCP server** is on `dokploy-network` in prod — point your reverse proxy (nginx/Caddy/Traefik) to port 8001 and expose it as `https://mcp.yourdomain.com`
- **Fetch agent** is on the `internal` network only — it makes outbound connections to Agentverse; no inbound port needed
- Both services restart automatically (`restart: always`) and wait for the backend healthcheck before starting
- Rotate API keys at any time from **Settings → API Keys** without restarting VoxlyAI — just update the env var and restart the affected service
