#!/usr/bin/env bash
set -euo pipefail

# Single entry point for local development.
# Usage:
#   ./dev.sh up       — Start deps, pull model, ingest docs, run server
#   ./dev.sh down     — Stop all containers
#   ./dev.sh ingest   — Re-ingest docs into Qdrant (must be running)
#   ./dev.sh server   — Run just the server (deps must be running)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Load config from .env
LLM_BACKEND=$(grep -E '^LLM_BACKEND=' .env 2>/dev/null | cut -d= -f2 || echo "ollama")
OLLAMA_MODEL=$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2 || echo "llama3.2")

# Ensure venv exists and is active
if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]" --quiet
fi
# shellcheck disable=SC1091
source .venv/bin/activate

wait_for_qdrant() {
    echo "Waiting for Qdrant to be ready..."
    for _i in $(seq 1 30); do
        if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
            echo "Qdrant is ready."
            return 0
        fi
        sleep 1
    done
    echo "ERROR: Qdrant did not become ready in 30 seconds."
    exit 1
}

wait_for_ollama() {
    echo "Waiting for Ollama to be ready..."
    for _i in $(seq 1 60); do
        if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "Ollama is ready."
            return 0
        fi
        sleep 1
    done
    echo "ERROR: Ollama did not become ready in 60 seconds."
    exit 1
}

ensure_ollama() {
    # Check if Ollama is already running (native install)
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is already running (native)."
    else
        echo "Ollama not detected — starting via Docker..."
        docker compose --profile ollama up -d
        wait_for_ollama
    fi

    # Ensure the model is available
    if curl -sf http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
tags = json.load(sys.stdin)
models = [m['name'] for m in tags.get('models', [])]
sys.exit(0 if any('$OLLAMA_MODEL' in m for m in models) else 1)
" 2>/dev/null; then
        echo "Model $OLLAMA_MODEL is available."
    else
        echo "Pulling model $OLLAMA_MODEL (this may take a few minutes on first run)..."
        curl -sf http://localhost:11434/api/pull -d "{\"name\": \"$OLLAMA_MODEL\", \"stream\": false}"
        echo ""
        echo "Model $OLLAMA_MODEL pulled."
    fi
}

cmd_up() {
    echo "==> Starting Qdrant..."
    docker compose up -d

    wait_for_qdrant

    if [ "$LLM_BACKEND" = "ollama" ]; then
        echo "==> Setting up Ollama..."
        ensure_ollama
    fi

    echo "==> Ingesting docs into Qdrant..."
    python scripts/ingest.py

    echo ""
    kill_server
    echo "==> Starting server on http://localhost:8000 (LLM_BACKEND=$LLM_BACKEND)..."
    echo "    Press Ctrl+C to stop the server. Run './dev.sh down' to stop containers."
    python -m src.main
}

kill_server() {
    local pid
    pid=$(lsof -ti:8000 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo "Killing existing process on port 8000 (pid $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
}

cmd_down() {
    echo "==> Stopping all services..."
    kill_server
    docker compose --profile ollama down
    echo "Done. All services stopped."
}

cmd_ingest() {
    wait_for_qdrant
    echo "==> Ingesting docs into Qdrant..."
    python scripts/ingest.py
}

cmd_server() {
    kill_server
    echo "==> Starting server on http://localhost:8000 (LLM_BACKEND=$LLM_BACKEND)..."
    python -m src.main
}

case "${1:-help}" in
    up)      cmd_up ;;
    down)    cmd_down ;;
    ingest)  cmd_ingest ;;
    server)  cmd_server ;;
    *)
        echo "Usage: ./dev.sh {up|down|ingest|server}"
        echo ""
        echo "  up      — Start Qdrant + Ollama, pull model, ingest docs, run server"
        echo "  down    — Stop all containers"
        echo "  ingest  — Re-ingest docs into Qdrant (must be running)"
        echo "  server  — Run just the server (deps must be running)"
        exit 1
        ;;
esac
