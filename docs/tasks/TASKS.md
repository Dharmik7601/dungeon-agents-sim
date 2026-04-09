# Tasks

## project-setup
- [x] Create `pyproject.toml` with all dependencies and dev tooling (google-generativeai, langfuse, rich, pytest, ruff)
- [x] Create `.env.example` listing all required environment variables
- [x] Create `prompts/agent_system.md` with the XML system prompt and `{{PLACEHOLDER}}` injection points
- [x] Integration tests for project-setup

## world
- [x] Implement `CellType` enum and `WorldState` dataclass (`src/world/state.py`)
- [x] Implement procedural map generation with obstacle density cap (`src/world/generator.py`)
- [x] Implement BFS validation and `generate_valid_world()` entry point (`src/world/generator.py`)
- [x] Integration tests for world

## agents
- [x] Implement `AgentState` dataclass with shadow map, inventory, message queues, and deadlock counters (`src/agents/state.py`)
- [x] Implement `ToolDispatcher` with all 7 tool handlers enforcing the ground-truth / shadow-state invariant (`src/agents/tools.py`)
- [x] Implement `LLMClient` wrapping the Google Generative AI SDK with prompt injection and JSON response parsing (`src/agents/llm_client.py`)
- [x] Integration tests for agents

## game-loop
- [x] Implement `GameLoop` orchestrator: turn sequencing, message delivery, end-condition checking (`src/loop/game_loop.py`)
- [x] Implement `run_simulation.py` entry point with terminal status printing (`src/loop/run_simulation.py`)
- [x] Integration tests for game-loop

## tracing
- [x] Implement `SemanticLogger`: event accumulation, delta computation (Scenario Mapping Matrix), JSON flush to `data/` (`src/tracing/semantic_logger.py`)
- [x] Implement Langfuse `@observe` wrapper and run metadata tagging (`src/tracing/langfuse_wrapper.py`)
- [x] Integration tests for tracing

## cli-viewer
- [x] Implement `diagnostic_viewer.py` with `argparse` CLI (`--log-file`, `--filter`, `--agent`) (`src/cli/diagnostic_viewer.py`)
- [x] Implement `rich` rendering: dim success lines and red Incident Blocks with diff + reasoning sections (`src/cli/diagnostic_viewer.py`)
- [x] Integration tests for cli-viewer

## end-to-end
- [x] End-to-end smoke test: run a full simulation, assert `run_*.json` is produced with valid schema, assert CLI viewer exits cleanly on that file

## prompt-context
- [x] Feature B: add `last_known_position` + `last_known_position_turn` to `AgentState`; update `_check_coordinates` to set them; inject `{{LAST_KNOWN_LOCATION}}` via `LLMClient` and prompt template
- [x] Feature C: add `last_mistake` to `AgentState`; record on tool failure and `ParseError` in `GameLoop`; inject `{{LAST_MISTAKE}}` into prompt
- [x] Feature D: add `recent_calls` (max 5) to `AgentState`; append after every dispatch in `GameLoop`; inject `{{RECENT_CALLS}}` into prompt
- [ ] Integration tests for prompt-context

## interrupt
- [ ] Feature A: add `EndCondition.INTERRUPTED`; `GameLoop` accepts `stop_event`; `run_simulation.py` spawns `msvcrt`-based daemon thread for Ctrl+E
- [ ] Integration tests for interrupt
