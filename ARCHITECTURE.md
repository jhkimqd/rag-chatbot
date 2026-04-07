# Architecture Specification: Polygon Hybrid Bot (v2.0)

## 1. System Overview

The Polygon Hybrid Bot is an enterprise-grade AI agent designed to bridge the gap between static documentation and real-time operational health. It uses a **Protocol Switch** architecture to route user input through three distinct processing lanes:

1. Deterministic Commands
2. Natural Language RAG
3. Real-Time Operational Tooling

### High-Level Flow

```text
┌──────────────────────────────────────────────────────────────────┐
│                   INPUT ROUTING (The Protocol Switch)            │
│                                                                  │
│  User Input (e.g., "/gas-usage" vs "How do I bridge?")           │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐       Match (/)      ┌──────────────────────┐   │
│  │ Regex       │─────────────────────►│   Command Registry   │   │
│  │ Dispatcher  │                      │ (Deterministic Logic)│   │
│  └──────┬──────┘                      └──────────┬───────────┘   │
│         │ No Match (Natural Language)            │               │
│         ▼                                        │               │
│  ┌─────────────┐       On-Topic       ┌──────────┴───────────┐   │
│  │ Input Guard │─────────────────────►│    Intent Manager    │   │
│  │ (Haiku)     │                      │  (Classifies Goal)   │   │
│  └──────┬──────┘                      └────┬────────────┬────┘   │
│         │                                  │            │        │
│         ▼                                  ▼            ▼        │
│  ┌────────────┐                    ┌───────────┐  ┌────────────┐ │
│  │ Reject /   │                    │ RAG Path  │  │  Ops Path  │ │
│  │ Redirect   │                    │ (Docs)    │  │ (Metrics)  │ │
│  └────────────┘                    └─────┬─────┘  └─────┬──────┘ │
│                                          │              │        │
│                                          ▼              ▼        │
│                                   ┌──────────────────────────┐   │
│                                   │    Response Synthesis    │   │
│                                   │ (Markdown + Charts + UI) │   │
│                                   └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Core Components

### 2.1 The Regex Dispatcher (Layer 0)

The entry point for all queries. It checks for a leading `/` to trigger the Command Registry.

- **Role:** Instant execution of high-precision business logic.
- **Bypass:** Skips all LLM classification to save latency (~<50ms) and cost ($0).

### 2.2 Command Registry (Plugin System)

A collection of deterministic tool-scripts mapped to slash commands.

- **Structure:** Each command is a modular plugin (e.g., `src/commands/gas_usage.py`).
- **Logic example:** `/gas-usage [start] [end]` fetches blocks via RPC and calculates:

$$
\text{Utilization \%} = \left( \frac{\text{block.gasUsed}}{\text{block.gasLimit}} \right) \times 100
$$

- **Visualization:** Returns pre-formatted UI components (charts/tables), not only plain text.

### 2.3 Intent Manager (Layer 1)

For non-command input, a Claude 3 Haiku call classifies intent into one of three buckets:

- `DOCS`: Technical "how-to" or "what is" questions.
- `OPS`: Questions about current network health (p95 latency, RPC status).
- `HYBRID`: Debugging that needs both docs and metrics (e.g., "The network is slow, what are the remediation steps?").

## 3. Data Pipelines

### 3.1 RAG Pipeline (Documentation)

- **Vector DB:** Qdrant or Pinecone.
- **Search:** Hybrid search (vector + BM25) over Polygon docs, GitHub issues, and runbooks.
- **Freshness:** Re-indexed daily via GitHub Actions.

### 3.2 Tool-Calling Agent (Operations)

- **Model:** Claude 3.5 Sonnet (optimized for reasoning over tool outputs).
- **Tools:**
  - Datadog: `query_metrics`, `get_active_monitors`
  - Incident.io: `get_active_incidents`
  - Polygon Node: `get_chain_status` (RPC)

## 4. UI and Delivery

The bot supports multi-platform rendering:

- **Slack:** Adaptive cards (Block Kit) for first responders.
- **Web:** Interactive React components (Recharts) for deep-dive analysis.
- **Citations:** Every response must include a source tag (e.g., `[source: polygon-docs]` or `[source: datadog]`).

## 5. OKR Alignment and ROI

This architecture is designed to meet the H1 2026 Reliability OKR:

> Reduce manual observability toil for first responders by >=80%.

### Measurement Metrics

- **Command usage:** Tracking `/gas-usage` vs. manual Polygonscan visits.
- **Toil reduction:** Time saved by auto-pulling runbooks during active incidents.
- **Accuracy:** Percentage of grounded answers cited from official sources.

## 6. Implementation Phases

1. **Phase 1 (MVP):** Basic RAG over docs.
2. **Phase 2 (ChatOps):** Command Registry with `/gas-usage` and `/health`.
3. **Phase 3 (Agentic):** Full tool-calling integration with Datadog and Slack integration.
