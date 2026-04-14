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
- [x] Feature A: add `EndCondition.INTERRUPTED`; `GameLoop` accepts `stop_event`; `run_simulation.py` spawns `msvcrt`-based daemon thread for Ctrl+E
- [ ] Integration tests for interrupt

## analysis-cli

### single-run-analysis
- [x] Scaffold `src/cli/single_run_analysis.py`: argparse entry point, load and validate log file, `main()` shell
- [x] Metric A — Run Outcome & Duration: `derive_end_condition(events)`, total turns, final grid distance if not SUCCESS
- [x] Metric B — Agent Efficiency: `compute_agent_efficiency(events)` — action breakdown, error rate, chatter volume per agent
- [x] Metric C — Delusion Timeline: `compute_delusion_timeline(events)` — chronological delta list with time-to-correction per cell key
- [x] Metric D — Map Coverage: `compute_map_coverage(events)` — union of both agents' final shadow states as % of 64 cells
- [x] Render single-run report: wire all metrics into `rich` tables and panels

### cross-run-analysis
- [x] Scaffold `src/cli/cross_run_analysis.py`: argparse entry point (default dir: `saved_logs/`), load all `run_*.json` files, `main()` shell
- [x] Metric A — Global Run Outcomes: success rate, avg completion turns, failure type distribution
- [x] Metric B — Top Failure Drivers: `compute_top_failure_drivers(all_events)` — property_key or error_message frequency, top 5
- [x] Metric C — Stubbornness Index: `compute_stubborn_failures(all_events)` — consecutive same-agent same-action failures as % of total failures
- [x] Metric D — Tool Reliability: `compute_tool_reliability(all_events)` — failure rate % per tool_name
- [x] Metric E — Average Exploration Density: mean map coverage across all runs
- [x] Render cross-run report: wire all metrics into `rich` tables and panels

### shared
- [x] Add `make analyze LOG=<path>` and `make analyze-all DIR=<path>` targets to Makefile
- [x] Integration tests for analysis-cli

## bugfix-compute-deltas

### fix-1-oob-sparse-fallback
- [x] Guard sparse-snapshot "empty" fallback with bounds check in `_compute_deltas`
- [x] Integration tests for fix-1-oob-sparse-fallback

### fix-2-move-position-keys
- [ ] Extend `move` branch of `_compute_deltas` to check `agent_position` and `partner_position` keys
- [ ] Integration tests for fix-2-move-position-keys

### fix-3-pickup-inventory-key
- [ ] Add `agent_inventory` to `pick_up` branch of `_compute_deltas`; thread inventory snapshot through `log_event` and `GameLoop`
- [ ] Integration tests for fix-3-pickup-inventory-key

### fix-4-prompt-target-cell
- [ ] Add one sentence to `prompts/agent_system.md` instructing the LLM to reference the move target cell in `expected_state`
- [ ] Integration tests for fix-4-prompt-target-cell
