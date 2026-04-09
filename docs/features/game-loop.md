# Game Loop

## What It Does
Orchestrates the entire simulation run: sequences turns (Agent A → Agent B), delivers delayed messages at the start of each round, drives the per-turn LLM → tool → log pipeline, checks all 4 end conditions after each agent acts, and prints lightweight terminal status so the operator can see progress.

## Implementation

**`src/loop/game_loop.py`** — three types + one class:
- `EndCondition` (Enum): `SUCCESS`, `TURN_LIMIT`, `ACTION_DEADLOCK`, `PARSE_DEADLOCK`
- `RunResult` (dataclass): `end_condition`, `turn_number`, `log_path`
- `GameLoop(world, agent_a, agent_b, llm_a, llm_b, logger, max_turns=50)` — the orchestrator

Each round: `_deliver_messages` is called for both agents first (moves partner outbox → agent inbox and clears outbox, enforcing the one-turn message delay). Then Agent A acts, then Agent B acts. After each agent's turn, success and deadlock conditions are checked. `world.turn_number` increments after both agents have acted.

**Message delivery invariant**: `_deliver_messages(agent, partner)` moves `partner.message_outbox` into `agent.message_inbox`. Both deliveries happen at the start of the round — before either agent acts — so messages sent in round N are visible to the recipient in round N+1 only.

**End conditions**:
- `PARSE_DEADLOCK`: caught when `consecutive_parse_failures >= 3` after a `ParseError` from the LLM client
- `ACTION_DEADLOCK`: checked after tool dispatch when `consecutive_invalid_actions >= 5`
- `SUCCESS`: both agents at `exit_pos` and `exit_locked is False`
- `TURN_LIMIT`: `world.turn_number >= max_turns`

**`src/loop/run_simulation.py`** — `run(run_id)` entry point. Generates world, instantiates agents and `LLMClient` objects, creates a `_PrintLogger` that prints one-line status per action, runs the `GameLoop`, prints end-condition summary.

## Key Files
- `src/loop/game_loop.py`
  - `EndCondition` (Enum) — terminal conditions
  - `RunResult` (dataclass) — `end_condition`, `turn_number`, `log_path`
  - `GameLoop.run() -> RunResult`
  - `GameLoop._run_agent_turn(agent, llm, partner) -> EndCondition | None`
  - `GameLoop._deliver_messages(agent, partner)` — one-turn delay enforcement
  - `GameLoop._check_success() -> bool`
- `src/loop/run_simulation.py`
  - `run(run_id)` — CLI entry point with status printing

## Testing
- **Unit** — `EndCondition` has 4 members; `RunResult` fields; `_deliver_messages` moves outbox to inbox and clears; `_check_success` True/False variants; all 4 end conditions fire at correct thresholds; turn order A→B per round; logger called once per agent action; `turn_number` increments per round
- **Integration** — message sent by Agent A in round 0 is NOT in Agent B's inbox during round 0; arrives in round 1
- **Edge cases** — success detected immediately if both agents already at exit on `run()`; parse deadlock fires after third consecutive failure
