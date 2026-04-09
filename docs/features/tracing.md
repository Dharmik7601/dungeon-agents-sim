# Tracing

## What It Does
Produces two observability artifacts per run. `SemanticLogger` accumulates one structured event per agent action — capturing all three state layers plus computed deltas — and flushes the array to `data/run_{timestamp}.json` on completion. The Langfuse wrapper decorates every LLM call so latency, token usage, and raw I/O are captured automatically in the Langfuse backend, cross-referenced to semantic log events via shared `run_id` and `turn_number` metadata.

## Implementation

## Key Files

## Testing
- **Unit** — delta computation: for each tool in the Scenario Mapping Matrix, assert correct keys are evaluated and mismatches produce correctly structured `delta` objects with the right `discrepancy_source`; no delta produced when expected matches ground truth; `SemanticLogger.flush()` writes valid JSON array to `data/`; Langfuse wrapper passes correct metadata tags
- **Integration** — a scripted two-turn run produces a JSON file with exactly two events, each containing all required top-level keys; a known state mismatch (stale key position) produces a delta with `discrepancy_source: "stale_shadow_state"`
- **Edge cases** — `send_message` produces an event with an empty `deltas` array; `look` produces an event with an empty `deltas` array; run with zero failures produces a valid file with no failure events
