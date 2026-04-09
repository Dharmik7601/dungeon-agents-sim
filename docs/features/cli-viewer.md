# CLI Viewer

## What It Does
A standalone diagnostic replay tool that parses a `run_*.json` semantic log and renders a human-readable incident timeline in the terminal. Successful turns are printed as muted single-line entries. Failed turns are expanded into high-visibility Incident Blocks showing: what action was attempted, a unified diff of the state desync (from `execution_result.deltas`), and the agent's raw LLM reasoning. Supports filtering to failures only and scoping to a single agent.

## Implementation

## Key Files

## Testing
- **Unit** — `--filter failures_only` skips events with `execution_result.status == "success"`; `--agent Agent_A` skips Agent B events; Incident Block renders all three sections when deltas are present; success line uses dim style; missing optional fields (e.g. null `error_message`) do not raise
- **Integration** — running the viewer on a known `run_*.json` fixture produces output containing expected agent IDs, turn numbers, and delta property keys; exit code is 0 on valid input
- **Edge cases** — empty log file (zero events) exits cleanly with a message; log file with no failures and `--filter failures_only` prints nothing; non-existent `--log-file` path prints a clear error and exits with code 1
