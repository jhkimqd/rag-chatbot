# Polygon Ops Slack Bot

Internal Slack bot for Polygon network operations. Provides real-time network health, Datadog metrics, Incident.io integration, and slash commands — scoped to your Slack workspace.

## What it does

| Feature | Description |
|---------|-------------|
| `/health` | Network health (block height, gas price, sync, peers) |
| `/gas-usage [N]` | Gas utilization for last N blocks |
| `/help` | List commands |
| Natural language | "Is the network down?" "Check Datadog for RPC latency" |

Natural language questions are routed to a tool-calling agent that can query:
- **Polygon RPC** — chain status, block data
- **Datadog** — metrics, triggered monitors
- **Incident.io** — active incidents

## Local Testing (no Slack needed)

Test the full routing pipeline locally with Ollama — no Slack workspace or tokens required:

```bash
# From repo root (handles Ollama setup automatically)
./dev.sh bot

# Or from slackbot/
cd slackbot
cp .env.example .env   # defaults to LLM_BACKEND=ollama
./dev.sh cli
```

This starts an interactive REPL with the same routing as the real Slack bot:

```text
Polygon Ops Bot CLI (backend: ollama)
Commands: /health, /gas-usage [N], /help
Or ask a natural language question. Type 'quit' to exit.

You: /health
[route: command | source: polygon-rpc]
**Polygon PoS Network Health**
- **Latest block:** 72,145,231
- **Gas price:** 30.12 Gwei
...

You: /gas-usage 5
[route: command | source: polygon-rpc]
**Gas Utilization — Last 5 Blocks**
...
```

**What works with Ollama:** Slash commands (`/health`, `/gas-usage`, `/help`) work fully since they're deterministic RPC calls — no LLM needed.

**What's limited with Ollama:** Natural language queries go through the ops agent, but Ollama doesn't support tool-calling, so it won't query Datadog/Incident.io/RPC live data. Use `LLM_BACKEND=anthropic` for full tool-calling support.

## Slack Setup

### 1. Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Enable **Socket Mode** and generate an app-level token (`xapp-...`)
3. Under **OAuth & Permissions**, add scopes: `app_mentions:read`, `chat:write`, `im:history`
4. Install the app to your workspace and copy the bot token (`xoxb-...`)
5. Copy the signing secret from **Basic Information**

### 2. Configure

```bash
cd slackbot
cp .env.example .env
# Edit .env with your Slack tokens and optional Datadog/Incident.io keys
```

### 3. Run

```bash
./dev.sh up
```

This will:
- Start Ollama if using local LLM (or skip if using Anthropic API)
- Launch the Slack bot in socket mode

### LLM Backend

| Backend | Config | Notes |
|---------|--------|-------|
| **Ollama** (default) | `LLM_BACKEND=ollama` | Free, local. Model pulled automatically |
| **Anthropic API** | `LLM_BACKEND=anthropic` + `ANTHROPIC_API_KEY=sk-ant-...` | Production-grade |

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_BACKEND` | No | `ollama` (default) or `anthropic` |
| `OLLAMA_MODEL` | No | Ollama model name (default: `llama3.2`) |
| `ANTHROPIC_API_KEY` | If using Anthropic | Claude API key |
| `SLACK_BOT_TOKEN` | For Slack mode | Slack bot OAuth token |
| `SLACK_SIGNING_SECRET` | For Slack mode | Slack app signing secret |
| `SLACK_APP_TOKEN` | For Slack mode | Slack app-level token (socket mode) |
| `DATADOG_API_KEY` | No | Enables Datadog metrics tools |
| `INCIDENT_IO_API_KEY` | No | Enables Incident.io tools |
| `POLYGON_RPC_URL` | No | Default: `https://polygon-rpc.com` |

Slack tokens are only required when running the real Slack bot (`./dev.sh up`). The CLI mode (`./dev.sh cli`) works without them.

## Testing

```bash
cd slackbot
pip install -e ".[dev]"

# Unit tests
pytest -v

# Lint
ruff check src/ tests/

# Interactive testing (no Slack needed)
./dev.sh cli
```

## Architecture

```text
User message (Slack or CLI)
    │
    ▼
┌──────────────┐      Match (/)      ┌──────────────┐
│ Regex        │─────────────────────►│ Command      │
│ Dispatcher   │                      │ Registry     │
└──────┬───────┘                      └──────────────┘
       │ No match
       ▼
┌──────────────┐
│ Ops Agent    │──► Datadog, Incident.io, Polygon RPC
│ (Tool Loop)  │    (requires Anthropic backend for tool-calling)
└──────────────┘
```

No RAG pipeline, no public endpoint, no input/output guards needed -- Slack workspace membership is your auth boundary. The CLI mode uses the same routing for local testing.
