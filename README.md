# Polygon Hybrid Bot

AI-powered support chatbot for the Polygon ecosystem. Combines RAG over documentation with real-time operational tooling (Datadog, Incident.io, Polygon RPC).

For architectural details see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Prerequisites

- Python 3.10+
- [Anthropic API key](https://console.anthropic.com/)
- Docker (for Qdrant, or use Qdrant Cloud)

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd polygon-chatbot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# ANTHROPIC_API_KEY is optional in development — mock responses are returned without it

# Start Qdrant (vector DB)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Run the server
python -m src.main

# Run test command
# Natural language question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I deploy a contract on Polygon PoS?"}'

```

The API is now live at `http://localhost:8000`.

> **Dev mode:** Leave `ANTHROPIC_API_KEY` blank and the bot runs in mock mode — all LLM calls return a `[DEV MODE]` stub response so you can test routing, commands, and the API surface without spending API credits. Set `ENVIRONMENT=production` to make the key required.

## API Usage

### Chat

```bash
# Natural language question
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I deploy a contract on Polygon PoS?"}'

# Slash command
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "/health"}'

# Gas utilization (last 20 blocks)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "/gas-usage 20"}'

# With API key auth (if CHATBOT_API_KEY is set)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"message": "/help"}'
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

### Swagger Docs

Available at `http://localhost:8000/docs` in development mode (disabled when `ENVIRONMENT=production`).

## Slash Commands

| Command | Description |
|---------|-------------|
| `/health` | Network health summary (block height, gas price, sync status) |
| `/gas-usage [count]` | Gas utilization for the last N blocks (default: 10, max: 100) |
| `/help` | List available commands |

## Configuration

All config is via environment variables (or `.env` file). See [.env.example](.env.example) for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Anthropic API key for Claude |
| `QDRANT_URL` | No | Qdrant server URL (default: `http://localhost:6333`) |
| `CHATBOT_API_KEY` | No | If set, requires `X-API-Key` header on `/chat` |
| `ENVIRONMENT` | No | `development` (default) or `production` |
| `EMBEDDING_MODEL` | No | sentence-transformers model (default: `all-MiniLM-L6-v2`) |
| `SLACK_BOT_TOKEN` | No | Enables Slack integration |
| `DATADOG_API_KEY` | No | Enables Datadog metrics tools |
| `INCIDENT_IO_API_KEY` | No | Enables Incident.io tools |

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_protocol_switch.py -v

# Lint
ruff check src/ tests/

# Lint with auto-fix
ruff check --fix src/ tests/
```

Tests use mocks for all external services — no API keys or running services needed.

## Local Development

Full end-to-end local setup:

```bash
# 1. Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# 2. Set your Anthropic key
echo 'ANTHROPIC_API_KEY=sk-ant-your-key' > .env

# 3. Run the server in reload mode
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

# 4. Test it
curl -s http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "/health"}' | python -m json.tool
```

> **Note:** The embedding model (`all-MiniLM-L6-v2`) downloads automatically on first use (~80MB). Subsequent starts are instant.

## Production Deployment

### 1. Create a Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY data/ data/

RUN pip install --no-cache-dir .

# Pre-download the embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Build and push

```bash
# Authenticate with GCP
gcloud auth configure-docker

# Build
docker build -t gcr.io/YOUR_PROJECT/polygon-chatbot:latest .

# Push
docker push gcr.io/YOUR_PROJECT/polygon-chatbot:latest
```

### 3. Deploy to Cloud Run

Cloud Run or some dedicated VM + usual devops.

### 4. Qdrant in production

Use [Qdrant Cloud](https://cloud.qdrant.io/) (managed) or deploy on GKE:

```bash
# Set Qdrant Cloud URL in Cloud Run env
gcloud run services update polygon-chatbot \
  --set-env-vars "QDRANT_URL=https://your-cluster.qdrant.io" \
  --set-secrets "QDRANT_API_KEY=qdrant-api-key:latest"
```

## Project Structure

```
src/
├── main.py              # FastAPI app (auth, rate limiting, timeouts)
├── config.py            # Pydantic settings from env vars
├── commands/            # Slash command plugins (/health, /gas-usage, /help)
├── guard/               # Input guard (topic relevance filter)
├── router/              # Protocol Switch, intent classifier, regex dispatcher
├── rag/                 # RAG pipeline (embeddings, retriever, generation)
├── ops/                 # Tool-calling agent (Datadog, Incident.io, RPC)
├── synthesis/           # Response formatting and citations
└── integrations/        # Slack, Polygon RPC clients
```
