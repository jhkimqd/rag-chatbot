#!/usr/bin/env bash
set -euo pipefail

# Top-level dev script — manages Ollama and routes to each component.
# Usage:
#   ./dev.sh mcp       — Test MCP server tools with Ollama (interactive CLI)
#   ./dev.sh bot       — Test Slack bot routing with Ollama (interactive CLI)
#   ./dev.sh slack     — Run the actual Slack bot (needs Slack tokens)
#   ./dev.sh down      — Stop Ollama container
#   ./dev.sh test      — Run tests for both components

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"

ensure_ollama() {
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is already running."
    else
        echo "Ollama not detected — starting via Docker..."
        docker compose -f slackbot/docker-compose.yml up -d
        echo "Waiting for Ollama..."
        for _i in $(seq 1 60); do
            if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
                echo "Ollama is ready."
                break
            fi
            sleep 1
        done
    fi

    if ! curl -sf http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
tags = json.load(sys.stdin)
models = [m['name'] for m in tags.get('models', [])]
sys.exit(0 if any('$OLLAMA_MODEL' in m for m in models) else 1)
" 2>/dev/null; then
        echo "Pulling model $OLLAMA_MODEL..."
        curl -sf http://localhost:11434/api/pull -d "{\"name\": \"$OLLAMA_MODEL\", \"stream\": false}"
        echo "Done."
    fi
}

ensure_venvs() {
    # MCP server
    if [ ! -d mcp-server/.venv ]; then
        echo "Setting up MCP server venv..."
        python3 -m venv mcp-server/.venv
        mcp-server/.venv/bin/pip install -e "mcp-server/.[dev]" --quiet
    fi
    # Slack bot
    if [ ! -d slackbot/.venv ]; then
        echo "Setting up Slack bot venv..."
        python3 -m venv slackbot/.venv
        slackbot/.venv/bin/pip install -e "slackbot/.[dev]" --quiet
    fi
}

cmd_mcp() {
    ensure_ollama
    ensure_venvs
    echo ""
    cd mcp-server
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python test_cli.py --model "$OLLAMA_MODEL"
}

cmd_bot() {
    ensure_ollama
    ensure_venvs
    echo ""
    cd slackbot
    # shellcheck disable=SC1091
    source .venv/bin/activate
    LLM_BACKEND=ollama OLLAMA_MODEL="$OLLAMA_MODEL" python -m polygon_bot.cli
}

cmd_slack() {
    ensure_venvs
    cd slackbot
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m polygon_bot.main
}

cmd_down() {
    echo "Stopping Ollama..."
    docker compose -f slackbot/docker-compose.yml down
    echo "Done."
}

cmd_test() {
    ensure_venvs
    echo "==> Testing MCP server..."
    (cd mcp-server && source .venv/bin/activate && python -m pytest tests/ -v)
    echo ""
    echo "==> Testing Slack bot..."
    (cd slackbot && source .venv/bin/activate && python -m pytest tests/ -v)
}

case "${1:-help}" in
    mcp)     cmd_mcp ;;
    bot)     cmd_bot ;;
    slack)   cmd_slack ;;
    down)    cmd_down ;;
    test)    cmd_test ;;
    *)
        echo "Usage: ./dev.sh {mcp|bot|slack|down|test}"
        echo ""
        echo "  mcp     — Test MCP server tools with Ollama (interactive)"
        echo "  bot     — Test Slack bot routing with Ollama (interactive, no Slack needed)"
        echo "  slack   — Run the actual Slack bot (needs Slack tokens in slackbot/.env)"
        echo "  down    — Stop Ollama container"
        echo "  test    — Run tests for both components"
        exit 1
        ;;
esac
