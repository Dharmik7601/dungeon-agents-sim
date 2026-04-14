# Tracing

## What It Does
Produces two observability artifacts per run. `SemanticLogger` accumulates one structured event per agent action — capturing all three state layers plus computed deltas — and flushes the array to `data/run_{run_id}_{timestamp}.json` on completion. The Langfuse wrapper decorates every LLM call so latency, token usage, and raw I/O are captured in the Langfuse backend, cross-referenced to semantic log events via shared `run_id`, `turn_number`, and `agent_id` metadata.

## Implementation

**`src/tracing/semantic_logger.py`**

- `_ground_truth_snapshot(world)` — flattens `WorldState` into a **sparse** standardised key format: `cell_status_{x}_{y}` only for non-empty cells, `{agent_id}_position` for each agent, plus `grid_width` and `grid_height` so the board renderer always knows the full grid size. Empty cells are omitted; consumers treat missing `cell_status_*` keys as `"empty"`.
- `_compute_deltas(tool_name, expected_state, shadow_state_before, world, agent_pos)` — Scenario Mapping Matrix: evaluates only the keys relevant to the tool called. For each mismatch between `expected_state` and ground truth, emits a delta dict with `property_key`, `expected_value`, `actual_value`, `discrepancy_source`. Source classification: `"fog_of_war"` (cell not in shadow_state_before), `"stale_shadow_state"` (observed but outdated), `"hallucination"` (other). No-op tools (`look`, `check_*`, `send_message`) always produce empty deltas.
- `SemanticLogger.log_event(...)` — builds one event per schema: `event_id` (UUID), `timestamp` (ISO 8601), `action`, `state_context` (four layers: `agent_beliefs`, `shadow_state`, `ground_truth`, `agent_input`), `execution_result` (status, error_message, deltas). `agent_input` captures the prompt context at call time: `message_inbox`, `recent_calls` (snapshot before this action), `last_mistake` (snapshot before this action), `last_known_location` (position + turn_number from last `check_coordinates` call, or null). Appends to internal `_events` list.
- `SemanticLogger.flush(run_id)` — serialises `_events` to `data/run_{run_id}_{ts}.json`, creates the `data/` directory if missing, deletes the WIP file, returns the file path.

**`src/tracing/langfuse_wrapper.py`**

- `wrap_with_langfuse(llm_client, run_id, turn_number, agent_id)` — returns a decorated `get_decision` callable. If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` env vars are absent, returns the original method unchanged (transparent no-op). If present, uses the Langfuse v4 API: two nested `start_as_current_observation()` context managers — outer `as_type="span"` (trace), inner `as_type="generation"` (LLM call). Output is written via `generation.update(output=...)` before the context exits. Calls `lf.flush()` after each generation for real-time dashboard delivery. `atexit.register(lf.flush)` guards against crash data loss.

**`run_simulation.py` integration** — `_CompositeLogger` prints status lines to stdout AND delegates to `SemanticLogger`. Both LLM clients are wrapped with `wrap_with_langfuse`. The log file path is printed at the end of the run.

## Key Files
- `src/tracing/semantic_logger.py`
  - `_ground_truth_snapshot(world) -> dict`
  - `_compute_deltas(tool_name, expected_state, shadow_state_before, world, agent_pos) -> list[dict]`
  - `SemanticLogger.log_event(*, turn_number, agent_id, llm_response, shadow_state_before, tool_result, world, message_inbox=None, recent_calls_before=None, last_mistake_before=None, last_known_location_before=None)`
  - `SemanticLogger.flush(run_id="") -> str`
- `src/tracing/langfuse_wrapper.py`
  - `wrap_with_langfuse(llm_client, run_id, turn_number, agent_id) -> Callable`

## Bug Fixes

### bugfix-compute-deltas (branch: bugfix-compute_deltas)

Four bugs that caused `_compute_deltas` to return an empty list for the majority of real failure events, making the diagnostic viewer's "State Desync Diff" useless.

| # | Status | Location | Description |
|---|---|---|---|
| 1 — OOB sparse fallback | **done** | `semantic_logger.py` | **Before:** missing `cell_status_*` keys were blindly defaulted to `"empty"`, masking mismatches where the LLM expected an OOB cell. **After:** the default only applies when `0 <= cx < grid_w and 0 <= cy < grid_h`; OOB keys stay `None` so the mismatch fires. **Why:** the sparse snapshot omits empty cells as an optimisation, but that same omission should not paper over cells that don't exist at all. |
| 2 — `agent_position` / `partner_position` ignored | **pending** | `semantic_logger.py` | The `move` branch only collected `cell_status_*` keys. `agent_position` and `partner_position` keys from `expected_state` were silently dropped. |
| 3 — `agent_inventory` ignored for `pick_up` | **pending** | `semantic_logger.py` | The `pick_up` branch only collected `cell_contents_*` keys. The LLM uses `agent_inventory` instead; these were silently dropped. Fix requires threading an inventory snapshot through `log_event` and `GameLoop`. |
| 4 — LLM references wrong cell in `expected_state` | **pending** | `prompts/agent_system.md` | ~14/41 failures had a `cell_status_*` key referencing a random nearby cell instead of the move target, producing empty deltas by coincidence. A prompt instruction added to enforce the correct key. |

*Each row will be updated to **done** with before/after details once implemented.*

## Testing
- **Unit** — `_ground_truth_snapshot` produces correct cell and agent keys (sparse: no empty cells), includes `grid_width`/`grid_height`, omits `cell_status_*` keys for empty cells; `_compute_deltas` treats missing cell keys as "empty" (no spurious delta); `_compute_deltas` for `move` (no mismatch, wall mismatch, fog-of-war); for `pick_up` (stale shadow); for `use_item` (inventory mismatch); no-op tools produce empty deltas; `log_event` produces event with all required schema keys including `state_context.agent_input`; `agent_input` contains correct `message_inbox`, `recent_calls`, `last_mistake`, `last_known_location`; defaults to empty/null values when kwargs not provided; `flush` writes valid JSON array, creates missing dir, handles empty event list; unique `event_id` per event
- **Integration** — known `stale_shadow_state` mismatch appears in `execution_result.deltas`; Langfuse wrapper falls back gracefully when env vars absent; Langfuse v4 API path verified via mock
- **Edge cases** — `fog_of_war` when cell absent from shadow_state_before; empty flush produces `[]`; data dir auto-created
