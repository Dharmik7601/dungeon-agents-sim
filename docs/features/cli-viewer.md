# CLI Viewer

## What It Does
A standalone diagnostic replay tool that parses a `run_*.json` semantic log and renders a human-readable incident timeline in the terminal. Successful turns are printed as muted single-line entries. Failed turns are expanded into high-visibility Incident Blocks showing: what action was attempted, a unified diff of the state desync (from `execution_result.deltas`), and the agent's raw LLM reasoning.

## Implementation

**`src/cli/diagnostic_viewer.py`**

**argparse CLI:**
- `--log-file` (required) — path to semantic JSON log; prints to stderr and exits with code 1 if the file does not exist or contains invalid JSON
- `--filter` (optional, default `all`) — `all` | `failures_only`
- `--agent` (optional) — `agent_a` | `agent_b` — restrict output to one agent

**Rendering logic:**
- Load and parse JSON file.
- Iterate events in order, applying `--filter` and `--agent` filters.
- For each passing event:
  - **Success** → `rich.text.Text` with `dim` style: `[Turn X] {agent_id} ✓ {tool_name}({args})`
  - **Failure** → `rich.panel.Panel` with red border containing three sections:
    1. **What Happened** — tool + args from `action`
    2. **State Desync Diff** — rendered from `execution_result.deltas`; each delta shown as `EXPECTED: {key} = {expected_value}` / `ACTUAL: {key} = {actual_value}` / `Source: {discrepancy_source}`
    3. **Agent Reasoning** — italicised quote from `state_context.agent_beliefs.reasoning`

**Exit codes:** 0 on success, 1 on missing file or invalid JSON.

## Key Files
- `src/cli/__init__.py` — empty package init
- `src/cli/diagnostic_viewer.py` — full CLI tool
  - `main(argv=None)` — entry point; parses args, calls `render_log`
  - `render_log(events, filter_mode, agent_filter, console)` — iterates and renders events
  - `render_success(event, console)` — dim single-line Text
  - `render_incident(event, console)` — red Panel with three sections
  - `_fmt_diff(deltas)` — formats delta list as EXPECTED/ACTUAL/Source diff string
- `tests/test_cli_viewer.py` — full test suite

## Testing
- **Unit** — `_fmt_diff` formats property key, discrepancy source, EXPECTED/ACTUAL labels, multiple deltas, and empty list; `render_success` renders turn number, agent ID, tool name as dim Text (not a Panel); `render_incident` prints a Panel containing tool name, reasoning, delta property key, and discrepancy source
- **Integration** — `render_log` with `all` calls both renderers; `failures_only` skips success events; `--agent` filter skips the other agent; empty event list and all-success list with `failures_only` render nothing; `main()` on a mixed log exits 0; `--agent` and `--filter` flags accepted together
- **Edge cases** — non-existent `--log-file` prints a clear error to stderr and exits 1; invalid JSON exits 1; empty log exits 0; `failures_only` on a log with no failures exits 0
