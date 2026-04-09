# Tracing

## What It Does
Produces two observability artifacts per run. `SemanticLogger` accumulates one structured event per agent action — capturing all three state layers plus computed deltas — and flushes the array to `data/run_{run_id}_{timestamp}.json` on completion. The Langfuse wrapper decorates every LLM call so latency, token usage, and raw I/O are captured in the Langfuse backend, cross-referenced to semantic log events via shared `run_id`, `turn_number`, and `agent_id` metadata.

## Implementation

**`src/tracing/semantic_logger.py`**

- `_ground_truth_snapshot(world)` — flattens `WorldState` into the standardised key format: `cell_status_{x}_{y}` for every cell, `{agent_id}_position` for each agent.
- `_compute_deltas(tool_name, expected_state, shadow_state_before, world, agent_pos)` — Scenario Mapping Matrix: evaluates only the keys relevant to the tool called. For each mismatch between `expected_state` and ground truth, emits a delta dict with `property_key`, `expected_value`, `actual_value`, `discrepancy_source`. Source classification: `"fog_of_war"` (cell not in shadow_state_before), `"stale_shadow_state"` (observed but outdated), `"hallucination"` (other). No-op tools (`look`, `check_*`, `send_message`) always produce empty deltas.
- `SemanticLogger.log_event(...)` — builds one event per the `agent_trace_plan.md` schema: `event_id` (UUID), `timestamp` (ISO 8601), `action`, `state_context` (three layers), `execution_result` (status, error_message, deltas). Appends to internal `_events` list.
- `SemanticLogger.flush(run_id)` — serialises `_events` to `data/run_{run_id}_{ts}.json`, creates the `data/` directory if missing, deletes the WIP file, returns the file path.

**`src/tracing/langfuse_wrapper.py`**

- `wrap_with_langfuse(llm_client, run_id, turn_number, agent_id)` — returns a decorated `get_decision` callable. If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` env vars are absent, returns the original method unchanged (transparent no-op). If present, uses the Langfuse v4 API: two nested `start_as_current_observation()` context managers — outer `as_type="span"` (trace), inner `as_type="generation"` (LLM call). Output is written via `generation.update(output=...)` before the context exits. Calls `lf.flush()` after each generation for real-time dashboard delivery. `atexit.register(lf.flush)` guards against crash data loss.

**`run_simulation.py` integration** — `_CompositeLogger` prints status lines to stdout AND delegates to `SemanticLogger`. Both LLM clients are wrapped with `wrap_with_langfuse`. The log file path is printed at the end of the run.

## Key Files
- `src/tracing/semantic_logger.py`
  - `_ground_truth_snapshot(world) -> dict`
  - `_compute_deltas(tool_name, expected_state, shadow_state_before, world, agent_pos) -> list[dict]`
  - `SemanticLogger.log_event(*, turn_number, agent_id, llm_response, shadow_state_before, tool_result, world)`
  - `SemanticLogger.flush(run_id="") -> str`
- `src/tracing/langfuse_wrapper.py`
  - `wrap_with_langfuse(llm_client, run_id, turn_number, agent_id) -> Callable`

## Testing
- **Unit** — `_ground_truth_snapshot` produces correct cell and agent keys; `_compute_deltas` for `move` (no mismatch, wall mismatch, fog-of-war); for `pick_up` (stale shadow); for `use_item` (inventory mismatch); no-op tools produce empty deltas; `log_event` produces event with all required schema keys and correct three-layer state context; `flush` writes valid JSON array, creates missing dir, handles empty event list; unique `event_id` per event
- **Integration** — known `stale_shadow_state` mismatch appears in `execution_result.deltas` of the logged event; Langfuse wrapper falls back gracefully when env vars absent; Langfuse v4 API path (`start_as_current_observation` × 2 + `update` + `flush`) verified via mock with configured env vars
- **Edge cases** — `fog_of_war` when cell absent from shadow_state_before; empty flush produces `[]`; data dir auto-created
