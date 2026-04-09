# dungeon-agents-sim

A multi-agent LLM simulation on a procedurally generated 8×8 grid dungeon. The primary goal is generating deep, structured observability traces of agent decision-making — specifically capturing the delta between each agent's belief state and ground truth reality. Two AI agents (powered by Gemma 4) explore the dungeon, coordinate via delayed messaging, and produce a rich semantic JSON log that can be replayed with a standalone CLI diagnostic viewer.

## How to Use

- Install dependencies: `pip install -e ".[dev]"`
- Configure environment: copy `.env.example` to `.env` and fill in values
- Run a simulation: `python -m src.loop.run_simulation`
- View a diagnostic replay: `python -m src.cli.diagnostic_viewer --log-file data/run_<timestamp>.json`
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
│   ├── tracing/         # SemanticLogger, Langfuse @observe wrapper
│   └── cli/             # diagnostic_viewer.py (rich + argparse)
├── prompts/             # agent_system.md — XML system prompt with placeholders
├── data/                # output run_*.json semantic logs (gitignored)
└── tests/               # pytest test suite
```

## Key Files

- `CLAUDE.md` — this file, project orientation for humans and Claude
- `docs/DESIGN.md` — architecture, three-layer state model, decisions, alternatives
- `docs/tasks/TASKS.md` — task checklist, updated after each sub-task
- `docs/features/<name>.md` — per-feature detail: implementation and tests
- `prompts/agent_system.md` — XML system prompt injected before every LLM call

## Environment Variables

- `GOOGLE_API_KEY` — Google Generative AI API key (Gemma 4)
- `LANGFUSE_PUBLIC_KEY` — Langfuse project public key
- `LANGFUSE_SECRET_KEY` — Langfuse project secret key
- `LANGFUSE_HOST` — Langfuse host URL (defaults to cloud if unset)

## Conventions

- Three-layer state separation is a hard invariant: Ground Truth, Shadow State, Agent Beliefs are never mixed. See `docs/DESIGN.md`.
- Prompt files live in `prompts/` and use XML tags (`<system_prompt>`) with `{{PLACEHOLDER}}` string replacement. Never hardcode prompts in Python.
- LLM calls are always wrapped with the Langfuse `@observe` decorator in `src/tracing/`.
- All semantic trace events are appended to a `SemanticLogger` instance and flushed to `data/` on run completion.
- No hardcoded credentials or environment-specific values anywhere in source.
- Tests are written before implementation (TDD). Every module in `src/` has a corresponding `tests/test_<module>.py`.
