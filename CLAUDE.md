# dungeon-agents-sim

A multi-agent LLM simulation on a procedurally generated 8×8 grid dungeon. The primary goal is generating deep, structured observability traces of agent decision-making — specifically capturing the delta between each agent's belief state and ground truth reality. Two AI agents (powered by Gemma 4) explore the dungeon, coordinate via delayed messaging, and produce a rich semantic JSON log that can be replayed with a standalone CLI diagnostic viewer.

## How to Use

- Install dependencies: `pip install -r requirements.txt`
- Configure environment: copy `.env.example` to `.env` and fill in values
- Run a simulation: `python -m src.loop.run_simulation`
- Save a log for analysis: `make save LOG=data/run_<timestamp>.json`
- View a diagnostic replay: `python -m src.cli.diagnostic_viewer --log-file data/run_<timestamp>.json`
- Analyse a single run: `make analyze LOG=data/run_<timestamp>.json`
- Analyse all saved runs: `make analyze-all` (reads from `saved_logs/`)
- Launch Streamlit dashboard: `make streamlit` (reads logs from `saved_logs/`)
- Run tests: `pytest`
- Lint: `ruff check .`
- Format: `ruff format .`

## Project Structure

```
dungeon-agents-sim/
├── docs/
│   ├── DESIGN.md        # full design document — architecture and decisions
│   ├── features/        # one LLD file per feature
│   └── tasks/           # TASKS.md — current task progress
├── src/
│   ├── world/           # WorldState, CellType, procedural generation, BFS validation
│   ├── agents/          # AgentState, ToolDispatcher, LLMClient
│   ├── loop/            # GameLoop orchestrator, end-condition checker
│   ├── tracing/         # SemanticLogger (crash-safe), Langfuse @observe wrapper
│   └── cli/             # diagnostic_viewer.py, board_renderer.py, streamlit_app.py
├── prompts/             # agent_system.md — XML system prompt with placeholders
├── data/                # semantic logs — run_*.json (clean exit) or run_wip_*.json (crash)
├── saved_logs/          # logs archived here for dashboard and analysis tools
└── tests/               # pytest test suite
```

## Key Files

- `CLAUDE.md` — this file, project orientation for humans and Claude
- `docs/DESIGN.md` — architecture, three-layer state model, decisions, alternatives
- `docs/tasks/TASKS.md` — task checklist, updated after each sub-task
- `docs/features/<name>.md` — per-feature detail: implementation and tests
- `prompts/agent_system.md` — XML system prompt injected before every LLM call
- `src/cli/single_run_analysis.py` — per-run metrics: outcome, agent efficiency, delusion timeline, map coverage
- `src/cli/cross_run_analysis.py` — cross-run aggregate metrics: success rates, failure drivers, stubbornness, tool reliability, exploration density
- `src/cli/streamlit_app.py` — Streamlit web dashboard; delegates all metric computation to the two analysis modules above

## Environment Variables

- `GOOGLE_API_KEY` — Google Generative AI API key (required; used by Gemma model)
- `GEMINI_MODEL` — override the Gemma model name (default: `gemma-4-31b-it`)
- `LANGFUSE_PUBLIC_KEY` — Langfuse project public key (optional; leave blank to disable)
- `LANGFUSE_SECRET_KEY` — Langfuse project secret key (optional)
- `LANGFUSE_HOST` — Langfuse host URL (optional; defaults to cloud.langfuse.com)

## Conventions

- Three-layer state separation is a hard invariant: Ground Truth, Shadow State, Agent Beliefs are never mixed. See `docs/DESIGN.md`.
- Prompt files live in `prompts/` and use XML tags (`<system_prompt>`) with `{{PLACEHOLDER}}` string replacement. Never hardcode prompts in Python.
- LLM calls are wrapped with the Langfuse v4 API in `src/tracing/langfuse_wrapper.py` using nested `start_as_current_observation()` context managers (trace span → generation span); falls back to a no-op when env vars are absent.
- Semantic trace events are written to a crash-safe WIP file (`data/run_wip_*.json`) after every action. On clean exit the WIP is renamed to `data/run_{id}_{timestamp}.json` and deleted. A crash leaves the WIP file intact and readable by the diagnostic viewer.
- No hardcoded credentials or environment-specific values anywhere in source.
- Tests are written before implementation (TDD). Every module in `src/` has a corresponding `tests/test_<module>.py`.
- Run with `python -m src.loop.run_simulation` (not `python src/loop/run_simulation.py`) — the `-m` flag adds the project root to `sys.path` so `src.*` imports resolve correctly.
