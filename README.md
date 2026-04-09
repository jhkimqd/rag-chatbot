# Polygon Chatbot

AI-powered tools for the Polygon ecosystem, split into two independently deployable components:

| Component | Purpose | Audience | Cost |
|-----------|---------|----------|------|
| [MCP Server](mcp-server/) | Polygon docs + chain data as AI tools | Public | Zero (users bring their own AI) |
| [Slack Bot](slackbot/) | Ops agent with Datadog, Incident.io, RPC | Internal team | Your LLM API key only |

## Why this split?

A public chatbot is expensive to run, hard to secure from abuse, and exposes internal ops tooling. Instead:

- **MCP Server** — Users install it locally and query Polygon knowledge with their own AI (Claude, GPT, etc.). No hosting, no auth, no API costs for you.
- **Slack Bot** — Your team uses it in Slack for operational queries. Slack workspace membership is the auth boundary. Datadog and Incident.io credentials stay internal.

## Local Development

Both components can be tested locally with [Ollama](https://ollama.com) -- no API keys or Slack workspace needed.

```bash
# Test MCP server tools with Ollama (interactive)
./dev.sh mcp

# Test Slack bot routing with Ollama (interactive, no Slack needed)
./dev.sh bot

# Run tests for both components
./dev.sh test

# Stop Ollama container
./dev.sh down
```

The first run sets up venvs, pulls the Ollama model, and starts an interactive REPL where you can type questions and see the full pipeline in action.

### dev.sh commands

| Command | Description |
|---------|-------------|
| `./dev.sh mcp` | Test MCP tools + Ollama (interactive REPL) |
| `./dev.sh bot` | Test Slack bot routing + Ollama (interactive REPL, no Slack needed) |
| `./dev.sh slack` | Run the real Slack bot (needs tokens in `slackbot/.env`) |
| `./dev.sh test` | Run pytest for both components |
| `./dev.sh down` | Stop Ollama container |

### With Claude Code (MCP Server)

```bash
cd mcp-server && pip install -e .
claude mcp add polygon-knowledge -- polygon-mcp
```

### With Slack (Slack Bot)

```bash
cd slackbot
cp .env.example .env
# Fill in Slack tokens + optional Datadog/Incident.io keys
./dev.sh up
```

## Repository Structure

```text
polygon-chatbot/
├── dev.sh                  # Top-level dev script (manages Ollama, routes to components)
├── data/docs/              # Polygon documentation (shared source of truth)
├── mcp-server/             # Public: MCP server for Polygon knowledge
│   ├── src/polygon_mcp/
│   │   ├── server.py       # MCP tools + resources
│   │   ├── docs.py         # Doc loading, chunking, TF-IDF search
│   │   └── rpc.py          # Standalone Polygon RPC client
│   ├── test_cli.py         # Interactive CLI for testing with Ollama
│   └── tests/
├── slackbot/               # Internal: Slack bot for ops
│   ├── src/polygon_bot/
│   │   ├── main.py         # Slack Bolt app (Socket Mode)
│   │   ├── cli.py          # Interactive CLI for testing without Slack
│   │   ├── router.py       # Commands + ops agent dispatch
│   │   ├── commands/       # /health, /gas-usage, /help
│   │   ├── ops/            # Tool-calling agent (Datadog, Incident.io, RPC)
│   │   └── integrations/   # Polygon RPC client
│   ├── dev.sh              # Slack bot dev script
│   ├── docker-compose.yml  # Ollama container
│   └── tests/
├── ARCHITECTURE.md
└── README.md
```

## Architecture

```text
PUBLIC (zero hosting cost)              INTERNAL (Slack workspace)
┌─────────────────────────┐            ┌──────────────────────────┐
│  MCP Server             │            │  Slack Bot               │
│                         │            │                          │
│  Tools:                 │            │  /health                 │
│  - search_polygon_docs  │            │  /gas-usage              │
│  - get_polygon_chain_   │            │  "is the network down?"  │
│    status               │            │  "check datadog for..."  │
│  - get_gas_usage        │            │                          │
│                         │            │  Ops Agent Tools:        │
│  Resources:             │            │  - Datadog metrics       │
│  - docs://polygon/*     │            │  - Incident.io           │
│                         │            │  - Polygon RPC           │
│  User's own LLM ►──────│            │  - Monitor alerts        │
│  User's own API key     │            │                          │
└─────────────────────────┘            └──────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design rationale and each component's README for detailed setup.
