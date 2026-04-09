#!/usr/bin/env bash
set -euo pipefail

# Single entry point for local development of the Polygon Ops Slack Bot.
# Usage:
#   ./dev.sh up       — Start Ollama (if needed) + run the Slack bot
#   ./dev.sh cli      — Start Ollama (if needed) + interactive CLI (no Slack needed)
#   ./dev.sh down     — Stop Ollama container

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
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is already running (native)."
    else
        echo "Ollama not detected — starting via Docker..."
        docker compose up -d
        wait_for_ollama
    fi

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
    if [ "$LLM_BACKEND" = "ollama" ]; then
        echo "==> Setting up Ollama..."
        ensure_ollama
    fi

    echo ""
    echo "==> Starting Polygon Ops Slack Bot (LLM_BACKEND=$LLM_BACKEND)..."
    echo "    Press Ctrl+C to stop."
    python -m polygon_bot.main
}

cmd_cli() {
    if [ "$LLM_BACKEND" = "ollama" ]; then
        echo "==> Setting up Ollama..."
        ensure_ollama
    fi

    echo ""
    python -m polygon_bot.cli
}

cmd_down() {
    echo "==> Stopping Ollama..."
    docker compose down
    echo "Done."
}

case "${1:-help}" in
    up)      cmd_up ;;
    cli)     cmd_cli ;;
    down)    cmd_down ;;
    *)
        echo "Usage: ./dev.sh {up|cli|down}"
        echo ""
        echo "  up      — Start Ollama (if needed) + run the Slack bot"
        echo "  cli     — Start Ollama (if needed) + interactive CLI (no Slack needed)"
        echo "  down    — Stop Ollama container"
        exit 1
        ;;
esac
