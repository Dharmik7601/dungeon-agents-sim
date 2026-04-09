# Agents

## What It Does
Manages the per-agent belief state (shadow map, inventory, message queues, deadlock counters), executes validated tool calls against ground truth, and drives the LLM API call with prompt injection and structured JSON response parsing. This feature is the enforcement point for the three-layer state invariant: shadow state is updated only as an explicit side-effect of a tool call, never passively.

## Implementation

## Key Files

## Testing
- **Unit** — `AgentState` initialises with empty shadow map and zero deadlock counters; each `ToolDispatcher` handler: success path mutates ground truth correctly, failure path returns correct error without mutating state, shadow state updated only for the calling agent; `LLMClient` prompt injection replaces all placeholders; JSON parser extracts `reasoning`, `expected_state`, `tool_name`, `arguments` correctly; malformed JSON increments parse-failure counter
- **Integration** — `pick_up` by Agent A leaves Agent B's shadow map stale until Agent B calls `look`; `send_message` places message in outbox (not inbox) until next turn delivery; `move` into a wall returns failure without moving agent
- **Edge cases** — unknown tool name returns failure; `pick_up` on empty cell returns failure; `use_item` with item not in inventory returns failure; LLM returns non-JSON 3× triggers parse deadlock
