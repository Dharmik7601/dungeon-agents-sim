# Analysis CLI






## What It Does

Two standalone scripts that analyze the semantic JSON logs produced by the simulation:

- `single_run_analysis.py` — deep statistical summary of one run: outcome, agent efficiency, delusion timeline, and map coverage.
- `cross_run_analysis.py` — aggregate behavioral trends across a directory of runs: global outcomes, top failure drivers, stubbornness index, tool reliability, and average exploration density.

Both scripts use `rich` for terminal output and operate on the existing `run_*.json` log format. No new dependencies.


## Implementation

### Makefile targets + integration tests
`make analyze LOG=<path>` (guarded) and `make analyze-all [DIR=<path>]` (defaults to `saved_logs/`) added to `Makefile`. Both scripts use `sys.stdout.reconfigure(encoding="utf-8")` + `Console(legacy_windows=False)` to handle Windows cp1252 encoding. Integration tests in `tests/test_analysis_cli_integration.py` verify both success and error paths for each script using real saved logs.

### cross_run_analysis — all metrics
`src/cli/cross_run_analysis.py` loads all `run_*.json` files from a directory (`--dir`, default `saved_logs/`) via `load_all_runs`, exiting if none found. All metrics receive `runs: list[list[dict]]`:
- **Metric A** (`compute_global_outcomes`) — reuses `derive_end_condition`; counts SUCCESS/TURN_LIMIT/OTHER; avg completion turns over successes only.
- **Metric B** (`compute_top_failure_drivers`) — failure events: `property_key` per delta if deltas present, else `error_message`; `Counter.most_common(5)`.
- **Metric C** (`compute_stubborn_failures`) — per-run per-agent consecutive failure pairs with same `tool_name` + `arguments`; returns `{stubborn_count, total_failures, pct}`.
- **Metric D** (`compute_tool_reliability`) — total executions and failures per `tool_name` across all runs; failure rate %.
- **Metric E** (`compute_avg_exploration_density`) — reuses `compute_map_coverage` per run; averages `pct` across runs.
`main()` renders all five sections A→E with `console.rule()` separators.

### single_run_analysis — scaffold
`src/cli/single_run_analysis.py` provides an argparse entry point (`--log-file`) and `load_events(path)` which reads and validates the JSON log, exiting with an error message on file-not-found or decode failure. `main()` prints a header: `Analysis: <filename> — N events`.

### single_run_analysis — Metric C: Delusion Timeline
`compute_delusion_timeline(events)` scans all events with non-empty `deltas` and emits one record per delta: `{turn, agent_id, property_key, expected_value, actual_value, discrepancy_source, corrected_in}`. For `cell_status_*` keys, `corrected_in` is the turn gap until that agent's `shadow_state` reflects the `actual_value`, or `"never"`. Non-cell keys get `corrected_in = None`. `render_delusion_timeline` prints a rich table (section C) or a dim "no desyncs" message.

### single_run_analysis — Metric D: Map Coverage
`compute_map_coverage(events)` takes the last shadow_state per agent, unions all `cell_status_*` keys, and returns `{observed, total: 64, pct}`. `render_map_coverage` prints a rich table (section D). `main()` now calls all four sections A→D with `console.rule()` separators.

### single_run_analysis — Metric B: Agent Efficiency
`compute_agent_efficiency(events)` groups all events by `agent_id` using a `Counter` per tool name, tracking total actions, failure count, error rate %, and `send_message` chatter. `render_agent_efficiency` prints one rich table per agent (section B).

### single_run_analysis — Metric A: Run Outcome & Duration
`derive_end_condition(events)` inspects the final event's ground truth: if `exit_unlocked` cell exists and both agents are on it → `SUCCESS`; last turn >= 50 → `TURN_LIMIT`; else → `OTHER`. `compute_run_summary(events)` returns total turns, exit/key positions, and Manhattan distances from each agent's final position to the exit and (if key still on ground) to the key. `render_run_summary` prints this as a `rich` table (section A).

## Key Files

- `src/cli/cross_run_analysis.py` — cross-run analysis entry point
  - `load_all_runs(directory: Path) -> list[list[dict]]` — globs run_*.json, exits if none found
  - `compute_global_outcomes(runs) -> dict` — success rate, avg turns, failure distribution
  - `compute_top_failure_drivers(runs) -> list[tuple[str, int]]` — top-5 failure reasons by frequency
  - `compute_stubborn_failures(runs) -> dict` — consecutive same-action failure rate
  - `compute_tool_reliability(runs) -> dict[str, dict]` — per-tool failure rate
  - `compute_avg_exploration_density(runs) -> dict` — mean map coverage across runs
  - `render_*` counterpart for each metric
  - `main(argv: list[str] | None = None) -> None` — argparse CLI (`--dir`); renders sections A–E
- `src/cli/single_run_analysis.py` — single-run analysis entry point
  - `load_events(path: Path) -> list[dict]` — reads log file, validates JSON, exits on failure
  - `derive_end_condition(events: list[dict]) -> str` — classifies run as SUCCESS / TURN_LIMIT / OTHER
  - `compute_run_summary(events: list[dict]) -> dict` — outcome, turns, exit/key positions, Manhattan distances
  - `render_run_summary(summary: dict, console: Console) -> None` — rich table for section A
  - `compute_agent_efficiency(events: list[dict]) -> dict[str, dict]` — per-agent tool counts, error rate, chatter
  - `render_agent_efficiency(efficiency: dict[str, dict], console: Console) -> None` — rich tables for section B
  - `compute_delusion_timeline(events: list[dict]) -> list[dict]` — chronological delta records with time-to-correction
  - `render_delusion_timeline(timeline: list[dict], console: Console) -> None` — rich table for section C
  - `compute_map_coverage(events: list[dict]) -> dict` — union of final shadow states as % of 64 cells
  - `render_map_coverage(coverage: dict, console: Console) -> None` — rich table for section D
  - `main(argv: list[str] | None = None) -> None` — argparse CLI; loads events, prints header and sections A–D

## Testing

- **Unit** — `load_events` returns correct list from valid JSON file (`tests/test_single_run_analysis.py`)
- **Unit** — `load_events` raises `SystemExit` on missing file
- **Unit** — `load_events` raises `SystemExit` on invalid JSON
- **Unit** — `main()` prints header containing filename and event count
- **Unit** — `compute_agent_efficiency` returns correct tool counts, failure count, error rate per agent; chatter counts only send_message; zero error rate when no failures; single-action agent is valid
- **Unit** — `load_all_runs`: returns list of event lists from dir with two files; exits when no run_*.json found
- **Unit** — `compute_global_outcomes`: correct counts/rates across mixed SUCCESS/TURN_LIMIT/OTHER runs
- **Unit** — `compute_top_failure_drivers`: property_key when deltas present; error_message when no deltas; max 5 results; sorted by frequency
- **Unit** — `compute_stubborn_failures`: same-action consecutive failure → stubborn; different action → not stubborn; zero when no failures
- **Unit** — `compute_tool_reliability`: correct total, failure count, failure rate per tool
- **Unit** — `compute_avg_exploration_density`: single run returns its pct; multiple runs averaged correctly
- **Integration** — `single_run_analysis.main()` with real saved log: exits cleanly, renders sections A–D; exits non-zero on missing file
- **Integration** — `cross_run_analysis.main()` with `saved_logs/`: exits cleanly, renders sections A–E; exits non-zero on empty directory
- **Unit** — `compute_delusion_timeline`: single delta → one record with all fields; empty deltas → no records; multiple deltas in one event → multiple records; time-to-correction = N turns when shadow corrected; "never" when shadow never corrected; None for non-cell keys
- **Unit** — `compute_map_coverage`: union of both agents' final shadows; uses last shadow per agent; ignores non-cell-status keys; empty shadow contributes zero cells
- **Unit** — `derive_end_condition` returns SUCCESS / TURN_LIMIT / OTHER for each scenario; unlocked door without both agents present is not SUCCESS
- **Unit** — `compute_run_summary` returns correct total turns and Manhattan distances to exit
- **Unit** — `compute_run_summary` includes key distance when key still in GT; omits it when already picked up
