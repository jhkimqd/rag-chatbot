# Architecture: Polygon Chatbot (v3.0)

## Design Decision: Split Architecture

The original monolithic chatbot (v2) combined RAG documentation, operational tooling, and a public-facing API into one service. This created problems:

- **Cost exposure** -- Every public query triggered 3-4 LLM calls on our API key
- **Abuse surface** -- Rate limiting and guards can't fully prevent misuse at scale
- **Ops credential risk** -- Datadog/Incident.io keys sat behind a public endpoint

v3 splits into two independent components with clear boundaries.

## Component 1: MCP Server (Public)

A Model Context Protocol server that makes Polygon knowledge available to any MCP-compatible AI client (Claude Code, Claude Desktop, Cursor, etc.).

### How it works

```text
User's AI Client (Claude, GPT, etc.)
    │
    ▼
┌──────────────────────────────────┐
│  MCP Server (stdio transport)    │
│                                  │
│  Tools:                          │
│  ├─ search_polygon_docs(query)   │ → TF-IDF over bundled markdown
│  ├─ get_polygon_chain_status()   │ → JSON-RPC to public endpoint
│  └─ get_gas_usage(block_count)   │ → JSON-RPC block analysis
│                                  │
│  Resources:                      │
│  ├─ docs://polygon/list          │ → Document inventory
│  └─ docs://polygon/{name}        │ → Full document text
└──────────────────────────────────┘
```

### Key design choices

- **No vector DB** -- TF-IDF over ~150KB of docs is fast enough and eliminates the Qdrant dependency
- **No LLM calls** -- The user's own AI handles generation; we just provide search and data
- **No auth** -- Runs locally via stdio, so there's no network exposure
- **No guards** -- Users querying their own AI don't need prompt injection protection
- **Bundled docs** -- Markdown files are included in the pip wheel via hatch `force-include`, with env var (`POLYGON_DOCS_DIR`) and repo-checkout fallbacks

### Distribution

```bash
pip install polygon-mcp     # from PyPI (future)
polygon-mcp                 # runs on stdio
```

### Local testing

`test_cli.py` simulates the MCP-to-LLM flow locally: it searches docs and fetches chain data using the MCP tools directly, then sends combined context to Ollama for generation. Run via `./dev.sh mcp` from the repo root.

## Component 2: Slack Bot (Internal)

An ops-focused Slack bot that answers operational questions using a tool-calling agent.

### How it works

```text
Slack Message (or CLI input)
    │
    ▼
┌────────────────┐    Match (/)    ┌──────────────┐
│ Regex          │────────────────►│ Command      │
│ Dispatcher     │                 │ Registry     │
└───────┬────────┘                 │ /health      │
        │ No match                 │ /gas-usage   │
        ▼                          │ /help        │
┌────────────────┐                 └──────────────┘
│ Ops Agent      │
│ (Claude tool   │
│  calling loop) │
│                │
│ Tools:         │
│ ├─ get_chain_status        → Polygon JSON-RPC
│ ├─ query_datadog_metrics   → Datadog API
│ ├─ get_active_incidents    → Incident.io API
│ └─ get_active_monitors     → Datadog API
└────────────────┘
```

### Key design choices

- **No RAG pipeline** -- Documentation queries are handled by the MCP server now
- **No intent classifier** -- Everything is either a slash command or an ops question
- **No input/output guards** -- Slack workspace membership is the auth boundary
- **No public HTTP endpoint** -- Socket Mode only, no inbound webhooks needed
- **CLI mode for testing** -- `cli.py` routes through the same `route_input` function without needing Slack tokens

### Ollama limitation

The Ollama backend does not support tool-calling. When using `LLM_BACKEND=ollama`, the ops agent returns Ollama's text response directly without invoking tools (no live Datadog/Incident.io/RPC data). Slash commands (`/health`, `/gas-usage`) work fully regardless of backend since they're deterministic RPC calls. Use the Anthropic backend for full tool-calling support.

### What was removed from v2

| Component | Reason |
|-----------|--------|
| FastAPI `/chat` endpoint | No public API needed |
| RAG pipeline (Qdrant, embeddings, retriever) | Docs served via MCP server now |
| Input guard (topic filter, injection detection) | Slack workspace = trusted users |
| Output guard (response policy check) | Internal tool, trusted context |
| Intent manager (DOCS/OPS/HYBRID classifier) | All queries are ops; docs via MCP |
| API key auth + HTTP rate limiting | Slack handles auth; per-user rate limit remains |

## Shared Components

Both components use `data/docs/` as the source of truth for Polygon documentation. The MCP server bundles these into the pip wheel at build time; updates require a new release.

The Polygon RPC client exists in both packages (standalone in MCP, config-aware in Slack bot) to keep them independently deployable with no shared code dependency. Both versions use `asyncio.gather` for concurrent RPC calls.

## Local Development

```bash
./dev.sh mcp     # MCP tools + Ollama (interactive REPL)
./dev.sh bot     # Slack bot routing + Ollama (interactive REPL, no Slack needed)
./dev.sh test    # pytest for both components
./dev.sh down    # stop Ollama
```

The root `dev.sh` handles Ollama lifecycle (starts Docker container if not running, pulls model on first use) and sets up per-component venvs.

## Deployment

| Component | Deployment | Infra |
|-----------|-----------|-------|
| MCP Server | `pip install` on user's machine | None (local process) |
| Slack Bot | Container or VM in your infra | Ollama or Anthropic API key |
