# Design Document

## Overview

`dungeon-agents-sim` is a multi-agent LLM simulation on a procedurally generated 8×8 grid dungeon. Its primary goal is **not** gameplay — it is generating deep, structured observability traces of agent decision-making, specifically capturing the delta between an agent's belief state and ground truth reality.

---

## Architecture

### Three-Layer State Model (Core Invariant)

Every agent turn maintains three strictly separated state objects:

| Layer | Object | Updated by | Purpose |
|---|---|---|---|
| **Ground Truth** | `WorldState` | Tool execution results | Authoritative reality — never passed to agents directly |
| **Shadow State** | `AgentState.shadow_map` | Explicit agent tool calls (`look`, `check_coordinates`, `check_inventory`) | What the simulation has told this agent — injected into prompt |
| **Agent Beliefs** | Parsed from LLM JSON (`expected_state`) | LLM reasoning output | What the agent expects to be true before acting |

Shadow state is updated **only** as a side-effect of the agent calling specific tools. It does not auto-sync with ground truth. This intentional lag is the mechanism that produces observable state-desync bugs.

### Game Loop

Sequential, custom vanilla Python. No LangGraph or LangChain. Turn order: Agent A → Agent B → advance counter → check end conditions.

Message delivery is delayed by one turn (outbox → inbox on next turn), creating communication-based desync.

### Prompt System

- External XML prompt files: `prompts/agent_system.md`
- Format: `<system_prompt>...</system_prompt>` with string-replacement placeholders
- Placeholders: `{{AGENT_ID}}`, `{{TURN_NUMBER}}`, `{{SHADOW_MAP}}`, `{{INVENTORY}}`, `{{MESSAGES}}`
- LLM responds strictly in JSON: `{ "reasoning", "expected_state", "tool_name", "arguments" }`

### Observability Output

Two artifacts produced per run:
1. **Langfuse infra traces** — latency, tokens, raw I/O via `@observe` decorator
2. **Semantic JSON log** (`data/run_{timestamp}.json`) — full three-layer state + deltas per event

---

## Directory Structure

```
dungeon-agents-sim/
├── src/
│   ├── world/          # WorldState, CellType, procedural generation, BFS validation
│   ├── agents/         # AgentState, ToolDispatcher, LLMClient
│   ├── loop/           # GameLoop orchestrator, end-condition checker
│   ├── tracing/        # SemanticLogger, Langfuse wrapper
│   └── cli/            # diagnostic_viewer.py
├── prompts/            # agent_system.md (XML system prompt)
├── data/               # output run_*.json files (gitignored)
├── tests/              # pytest test suite
└── docs/
    ├── DESIGN.md        # this file
    ├── features/        # per-feature LLD files
    └── tasks/TASKS.md   # task checklist
```

---

## Key Decisions

### Vanilla Python game loop (no orchestration framework)
Chosen to maintain absolute programmatic control over turn order, message queues, and JSON state extraction. Framework abstractions would obscure the precise point where shadow state diverges from ground truth.

### String-replacement prompt templating (no Jinja2/LangChain)
Keeps prompt rendering auditable and dependency-free. The prompt file is human-readable in source control and the injection point is explicit.

### Langfuse for infra traces
Native LLM observability SDK with built-in UI, token tracking, and clean export. Configured entirely via environment variables.

### Custom JSON semantic log (not OpenTelemetry spans)
The three-layer state schema (`agent_beliefs`, `shadow_state`, `ground_truth`) is domain-specific and does not map cleanly to generic span attributes. A custom schema allows exact alignment with the CLI viewer's rendering logic.

---

## Alternatives Considered

| Decision | Alternative | Rejected because |
|---|---|---|
| Vanilla Python loop | LangGraph | Would hide turn-order control and message queue mechanics behind framework abstractions |
| String templating | Jinja2 | Extra dependency for a one-file concern; adds indirection over a trivial operation |
| Langfuse | OpenTelemetry | OTel requires more boilerplate for LLM-specific fields; Langfuse is purpose-built |
| Custom JSON log | Langfuse custom events | Langfuse events lack the structured three-layer state diff the CLI viewer depends on |

---

## Environment Variables

- `GOOGLE_API_KEY` — Google Generative AI API key (Gemma 4)
- `LANGFUSE_PUBLIC_KEY` — Langfuse project public key
- `LANGFUSE_SECRET_KEY` — Langfuse project secret key
- `LANGFUSE_HOST` — Langfuse host URL (defaults to cloud if unset)
