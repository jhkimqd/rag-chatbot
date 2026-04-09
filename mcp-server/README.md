# Polygon MCP Server

MCP (Model Context Protocol) server that gives any AI assistant access to Polygon blockchain knowledge. Users bring their own AI — no API keys, no hosting, no cost to you.

## What it provides

| Tool | Description |
|------|-------------|
| `search_polygon_docs` | Search across Polygon documentation (PoS, CDK, AggLayer, contracts, bridging, gas, validators, RPC) |
| `get_polygon_chain_status` | Live network status — block height, gas price, sync, peers |
| `get_gas_usage` | Gas utilization table for recent blocks |

Plus document resources at `docs://polygon/{topic}` for direct access to full docs.

## Install

### Claude Code / Claude Desktop

```bash
# From the repo
cd mcp-server
pip install -e .

# Then add to your Claude config:
claude mcp add polygon-knowledge -- polygon-mcp
```

Or add manually to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "polygon-knowledge": {
      "command": "polygon-mcp"
    }
  }
}
```

### From source

```bash
cd mcp-server
pip install -e ".[dev]"
polygon-mcp  # runs on stdio
```

## Local Testing with Ollama

Test the full pipeline locally — MCP tools search docs and fetch chain data, then Ollama generates the answer:

```bash
# From repo root (handles Ollama setup automatically)
./dev.sh mcp

# Or manually
cd mcp-server
pip install -e ".[dev]"
python test_cli.py --model llama3.2
```

This starts an interactive REPL:

```text
Polygon MCP Test CLI (model: llama3.2, ollama: http://localhost:11434)
Indexed 142 doc chunks from 9 files
Type a question, or 'quit' to exit.

You: How do I deploy a smart contract on Polygon PoS?
  Asking Ollama...

To deploy a smart contract on Polygon PoS, you can use Hardhat...
```

The CLI searches the bundled docs, optionally fetches live chain data, then sends the combined context to Ollama — the same flow Claude Code would use via MCP.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLYGON_RPC_URL` | `https://polygon-rpc.com` | Polygon JSON-RPC endpoint |
| `POLYGON_DOCS_DIR` | (bundled) | Override path to docs directory |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint (for test CLI) |

## Development

```bash
cd mcp-server
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## How it works

- Documentation markdown files from `data/docs/` are bundled into the pip wheel at build time
- A lightweight TF-IDF index is built at startup (no vector DB needed)
- RPC tools query the Polygon network directly via JSON-RPC using `asyncio.gather` for concurrent calls
- Everything runs locally -- no external services required
- Docs path resolution: `POLYGON_DOCS_DIR` env var > bundled `polygon_mcp/bundled_docs/` > repo `data/docs/`
