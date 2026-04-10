# dungeon-agents-sim

A multi-agent LLM simulation on a procedurally generated 8×8 grid dungeon. The primary goal is generating deep, structured observability traces of agent decision-making — specifically capturing the delta between each agent's belief state and ground truth reality. Two AI agents (powered by Gemma 4) explore the dungeon, coordinate via delayed messaging, and produce a rich semantic JSON log that can be replayed with a standalone CLI diagnostic viewer.

## Prerequisites

- Python 3.11+
- A Google Generative AI API key with access to `gemma-4-31b-it`
- (Optional) A Langfuse account for LLM infra tracing

## Setup

```bash
pip install -r requirements.txt
```
Edit .env and fill in GOOGLE_API_KEY and optionally LANGFUSE_* keys

## Running

**Run a simulation:**
```bash
make run
# or
python -m src.loop.run_simulation
```
Press `Ctrl+E` at any time to stop the simulation mid-run. The semantic log is preserved up to that point.

**Run multiple simulations in sequence:**
```bash
make batch          # runs 10 times by default
make batch RUNS=5   # or specify a count
```

**Replay a diagnostic log:**
```bash
make viewer LOG=data/run_<timestamp>.json
# or
python -m src.cli.diagnostic_viewer --log-file data/run_<timestamp>.json
```

Options:
- `--filter failures_only` — show only failed turns
- `--agent agent_a` or `--agent agent_b` — restrict output to one agent

**Analyse a single run:**
```bash
make analyze LOG=data/run_<timestamp>.json
# or
python -m src.cli.single_run_analysis --log-file data/run_<timestamp>.json
```

**Analyse all saved runs:**
```bash
make analyze-all
# or with a custom directory
make analyze-all DIR=saved_logs/
# or
python -m src.cli.cross_run_analysis --dir saved_logs/
```

**Run tests:**
```bash
make test
# or
pytest
```

## Project Structure

```
dungeon-agents-sim/
├── docs/
│   ├── DESIGN.md        # architecture, state model, key decisions
│   ├── features/        # one LLD file per feature
│   └── tasks/           # TASKS.md — task checklist
├── prompts/
│   └── agent_system.md  # XML system prompt with {{PLACEHOLDER}} variables
├── src/
│   ├── world/           # WorldState, CellType, procedural generation, BFS validation
│   ├── agents/          # AgentState, ToolDispatcher, LLMClient
│   ├── loop/            # GameLoop orchestrator, end-condition checker, run_simulation entry point
│   ├── tracing/         # SemanticLogger (crash-safe WIP writes), Langfuse @observe wrapper
│   └── cli/             # diagnostic_viewer.py, board_renderer.py
├── data/                # semantic logs — run_*.json (clean) or run_wip_*.json (crash recovery)
└── tests/               # pytest test suite
```

## How It Works

### Agents and State

Two agents (`agent_a`, `agent_b`) take turns on an 8×8 grid. Each agent has a limited view — it only knows cells it has explicitly observed. The simulation tracks four state layers:

| Layer | What it is |
|---|---|
| **Ground Truth** | Authoritative `WorldState` — never passed to agents directly |
| **Shadow State** | Cells the agent has observed via tool calls — injected into the prompt |
| **Agent Beliefs** | The agent's `expected_state` JSON — what it thinks will be true after acting |
| **Agent Input** | Prompt context at decision time: inbox, recent calls, last mistake, last known location |

The intentional lag between shadow state and ground truth is the mechanism that produces observable state-desync bugs — the core research output of this simulation.

### Tools

Agents call tools by responding in JSON: `{ "reasoning", "expected_state", "tool_name", "arguments" }`.

Available tools: `move`, `look`, `pick_up`, `use_item`, `check_coordinates`, `check_inventory`, `send_message`.

- `check_coordinates` updates the agent's confirmed location in the prompt
- `send_message` puts a message in the partner's inbox (delivered after a one-turn delay)

### Semantic Log

After every agent action, a structured event is appended to `data/run_wip_*.json`. On clean exit it is renamed to `data/run_{run_id}_{timestamp}.json`. A crash leaves the WIP file intact and readable by the diagnostic viewer.

Each event includes:
- The action taken and its spatial context
- All four state layers at decision time
- Computed deltas between `expected_state` and ground truth, classified as `fog_of_war`, `stale_shadow_state`, or `hallucination`

### Diagnostic Viewer

The viewer replays a semantic log as a terminal timeline:

- **Successful turns** — dim single-line summary with Input (what the agent knew) and Output (reasoning) sections
- **Failed turns** — red `INCIDENT` panel with Input / Output / Result sections, including the error message and state desync diff

Board is redrawn before each event from the `ground_truth` snapshot.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Google Generative AI API key |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public key — disabled if absent |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |
| `LANGFUSE_HOST` | No | Langfuse host URL (default: `cloud.langfuse.com`) |
