# Design Document

## Overview

`dungeon-agents-sim` is a multi-agent LLM simulation on a procedurally generated 8×8 grid dungeon. Its primary goal is **not** gameplay — it is generating deep, structured observability traces of agent decision-making, specifically capturing the delta between an agent's belief state and ground truth reality.

---

## Architecture

### State Model

Every agent turn maintains four strictly separated state layers:

| Layer | Object | Updated by | Purpose |
|---|---|---|---|
| **Ground Truth** | `WorldState` | Tool execution results | Authoritative reality — never passed to agents directly |
| **Shadow State** | `AgentState.shadow_map` | Explicit agent tool calls (`look`, `check_coordinates`, `check_inventory`) | What the simulation has told this agent — injected into prompt |
| **Agent Beliefs** | Parsed from LLM JSON (`expected_state`) | LLM reasoning output | What the agent expects to be true before acting |
| **Agent Input** | `state_context.agent_input` in the semantic log | Snapshotted by `GameLoop` before each dispatch | Prompt context at decision time: inbox, recent calls, last mistake, last known location |

Shadow state is updated **only** as a side-effect of the agent calling specific tools. It does not auto-sync with ground truth. This intentional lag is the mechanism that produces observable state-desync bugs.

### Game Loop

Sequential, custom vanilla Python. No LangGraph or LangChain. Turn order: Agent A → Agent B → advance counter → check end conditions.

Message delivery is delayed by one turn (outbox → inbox on next turn), creating communication-based desync. Messages survive only one round in the recipient's inbox — they are overwritten at the start of the next round whether or not the recipient acted on them.

### Prompt System

- External XML prompt files: `prompts/agent_system.md`
- Format: `<system_prompt>...</system_prompt>` with string-replacement placeholders
- Placeholders: `{{AGENT_ID}}`, `{{TURN_NUMBER}}`, `{{SHADOW_MAP}}`, `{{INVENTORY}}`, `{{MESSAGES}}`, `{{LAST_KNOWN_LOCATION}}`, `{{LAST_MISTAKE}}`, `{{RECENT_CALLS}}`
- `SHADOW_MAP` is cumulative — all cells ever observed are included, not just the most recent
- `LAST_KNOWN_LOCATION` — position + turn confirmed by the last `check_coordinates` call; `"(unknown)"` until first call
- `LAST_MISTAKE` — tool name, turn number, and failure reason from the most recent failed action; `"(none)"` if no failure yet
- `RECENT_CALLS` — up to 5 most recent tool calls with arguments and turn numbers (sliding window)
- LLM responds strictly in JSON: `{ "reasoning", "expected_state", "tool_name", "arguments" }`

### LLM Model

Both agents use `gemma-4-31b-it` via the `google-genai` SDK. The model name is read from the `GEMINI_MODEL` environment variable and defaults to `gemma-4-31b-it` if unset.

### Observability Output

Two artifacts produced per run:

1. **Langfuse infra traces** — latency, tokens, raw I/O via the Langfuse v4 API. Each call creates a parent trace span (`start_as_current_observation(as_type="span")`) with a nested generation span (`as_type="generation"`) carrying the prompt input, output, and model name. Tagged with `run_id`, `turn_number`, and `agent_id`. `lf.flush()` is called after every generation for real-time dashboard visibility. Falls back to a transparent no-op when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are absent.

2. **Semantic JSON log** — full state + deltas per event, stored in `data/`. Each event's `state_context` has four layers:
   - `agent_beliefs` — LLM reasoning and `expected_state` from the JSON response
   - `shadow_state` — all cells the agent has observed, serialised as `cell_status_{x}_{y}` keys
   - `ground_truth` — sparse snapshot of `WorldState`: only non-empty cells are included; `grid_width`/`grid_height` always present so consumers know the full board size without inferring it from cell keys
   - `agent_input` — prompt context captured at call time: `message_inbox`, `recent_calls` (last 5), `last_mistake`, `last_known_location` (position + turn from last `check_coordinates`, or null)
   - **During a run:** written incrementally to `data/run_wip_<uuid8>.json` after every agent action. This file survives a crash and can be opened directly with the diagnostic viewer.
   - **On clean exit:** events are written to `data/run_{run_id}_{timestamp}.json` and the WIP file is deleted.

### Terminal Display

The live simulation renders a `rich`-based board after every agent action (screen clears and redraws in place). The diagnostic viewer renders the board state captured in each event's `ground_truth` snapshot before displaying the event's success line or incident panel.

Board symbols: `A` agent_a · `B` agent_b · `✦` both at same cell · `K` key · `X` exit (locked) · `O` exit (open) · `█` wall · `·` empty

**Diagnostic viewer structure** — each event shows:
- **Success:** dim single-line header + `── Input ──` (last known location, shadow size, inbox, last mistake, recent calls) + `── Output ──` (reasoning)
- **Failure:** red `Panel` titled `INCIDENT — Turn N | agent_id` with `── Input ──`, `── Output ──` (reasoning + action), and `── Result ──` (error message + state desync diff)

---

## Directory Structure

```
dungeon-agents-sim/
├── src/
│   ├── world/          # WorldState, CellType, procedural generation, BFS validation
│   ├── agents/         # AgentState, ToolDispatcher, LLMClient
│   ├── loop/           # GameLoop orchestrator, end-condition checker, run_simulation entry point
│   ├── tracing/        # SemanticLogger (crash-safe WIP writes), Langfuse wrapper
│   └── cli/            # diagnostic_viewer.py, board_renderer.py
├── prompts/            # agent_system.md (XML system prompt)
├── data/               # run_*.json (clean) or run_wip_*.json (crash recovery)
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
Native LLM observability SDK with built-in UI, token tracking, and clean export. Configured entirely via environment variables; silently disabled when keys are absent.

### Custom JSON semantic log (not OpenTelemetry spans)
The three-layer state schema (`agent_beliefs`, `shadow_state`, `ground_truth`) is domain-specific and does not map cleanly to generic span attributes. A custom schema allows exact alignment with the CLI viewer's rendering logic.

### Crash-safe WIP writes (append-on-every-event)
`SemanticLogger` writes the full event list to `run_wip_*.json` after every `log_event` call. On clean exit the WIP is replaced by the final named file. This ensures no events are lost to a crash, at the cost of one file-write per agent action (acceptable for ≤100 events per run).

---

## Alternatives Considered

| Decision | Alternative | Rejected because |
|---|---|---|
| Vanilla Python loop | LangGraph | Would hide turn-order control and message queue mechanics behind framework abstractions |
| String templating | Jinja2 | Extra dependency for a one-file concern; adds indirection over a trivial operation |
| Langfuse | OpenTelemetry | OTel requires more boilerplate for LLM-specific fields; Langfuse is purpose-built |
| Custom JSON log | Langfuse custom events | Langfuse events lack the structured three-layer state diff the CLI viewer depends on |
| WIP file (full rewrite per event) | JSONL append | Full rewrite keeps the file always valid JSON (readable mid-run); JSONL would require a converter before the viewer can read it |

---

## Environment Variables

- `GOOGLE_API_KEY` — Google Generative AI API key (required)
- `GEMINI_MODEL` — override model name (default: `gemma-4-31b-it`)
- `LANGFUSE_PUBLIC_KEY` — Langfuse public key (optional)
- `LANGFUSE_SECRET_KEY` — Langfuse secret key (optional)
- `LANGFUSE_HOST` — Langfuse host URL (optional; defaults to cloud)
