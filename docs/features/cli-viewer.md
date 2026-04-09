# CLI Viewer

## What It Does
A standalone diagnostic replay tool that parses a `run_*.json` semantic log and renders a human-readable incident timeline in the terminal. Successful turns are printed as muted single-line entries. Failed turns are expanded into high-visibility Incident Panels with three explicit sections (Input / Output / Result) showing what information the agent had, what it decided, and what went wrong.

## Implementation

**`src/cli/diagnostic_viewer.py`**

**argparse CLI:**
- `--log-file` (required) — path to semantic JSON log; prints to stderr and exits with code 1 if the file does not exist or contains invalid JSON
- `--filter` (optional, default `all`) — `all` | `failures_only`
- `--agent` (optional) — `agent_a` | `agent_b` — restrict output to one agent

**Rendering logic:**

For each event (after applying `--filter` and `--agent`), the board state captured in `state_context.ground_truth` is rendered first using `board_renderer.render_board_from_snapshot`, followed by the event itself.

- **Success** → dim `rich.text.Text` lines:
  - Header: `[Turn X] {agent_id} ✓ {tool_name}({args})`
  - `── Input ──` section: last known location, shadow cell count, inbox messages, last mistake, recent calls
  - `── Output ──` section: agent reasoning quote

- **Failure** → `rich.panel.Panel` with red border and title `INCIDENT — Turn X | {agent_id}`, containing three labelled sections:
  - `── Input ──`: last known location, shadow cell count, inbox, last mistake, recent calls, full shadow state cell dump
  - `── Output ──`: agent reasoning, action (tool + args)
  - `── Result ──`: error message from `execution_result.error_message`, state desync diff from `execution_result.deltas`

**Exit codes:** 0 on success, 1 on missing file or invalid JSON.

## Key Files
- `src/cli/__init__.py` — empty package init
- `src/cli/diagnostic_viewer.py` — full CLI tool
  - `main(argv=None)` — entry point; parses args, calls `render_log`
  - `render_log(events, filter_mode, agent_filter, console)` — iterates events, renders board + event
  - `render_success(event, console)` — dim Input/Output sections as Text
  - `render_incident(event, console)` — red Panel with Input/Output/Result sections
  - `_fmt_diff(deltas) -> str` — formats delta list as EXPECTED/ACTUAL/Source diff string
  - `_fmt_location(loc) -> str` — formats `last_known_location` dict as `"(x, y) confirmed on turn N"` or `"(unknown)"`
  - `_fmt_input_lines(event, indent="  ") -> list[str]` — shared helper that builds Input section lines from `state_context.agent_input`: last known location, shadow cell count, inbox, last mistake, recent calls
- `tests/test_cli_viewer.py` — full test suite

## Testing
- **Unit** — `_fmt_diff` formats property key, discrepancy source, EXPECTED/ACTUAL labels, multiple deltas, and empty list; `_fmt_location` returns correct string when location present and `"(unknown)"` when None; `_fmt_input_lines` includes all five input fields; `render_success` renders turn number, agent ID, tool name, reasoning, and full Input section (location, shadow count, inbox, last mistake, recent calls); `render_incident` prints a red Panel containing Input/Output/Result sections with error message, delta property key, discrepancy source, reasoning, and shadow state cells; both renderers handle events without `agent_input` key without crashing
- **Integration** — `render_log` with `all` calls both renderers; `failures_only` skips success events; `--agent` filter skips the other agent; empty event list and all-success list with `failures_only` render nothing; `main()` on a mixed log exits 0; `--agent` and `--filter` flags accepted together
- **Edge cases** — non-existent `--log-file` prints a clear error to stderr and exits 1; invalid JSON exits 1; empty log exits 0; `failures_only` on a log with no failures exits 0
