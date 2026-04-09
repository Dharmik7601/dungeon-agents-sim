# Prompt Context Enrichment

## What It Does
Tracks three per-agent context fields that are injected into every LLM prompt:

1. **Last Known Location** — the position and turn number confirmed by the most recent `check_coordinates()` call. Remains stale until the tool is called again.
2. **Last Mistake** — the most recent failed tool call (tool name, turn, reason). Persists across turns until a new mistake replaces it.
3. **Recent Calls** — a sliding window of the 5 most recently dispatched tool calls (tool name, arguments, turn number), updated after every dispatch.

## Implementation

**Feature C — Last Mistake**: `AgentState` gains `last_mistake: dict | None = None`. `GameLoop._run_agent_turn` sets it in two places: in the `except ParseError` block (tool_name `"(parse_error)"`) and after dispatch when `result.status == "failure"`. Successful dispatches leave `last_mistake` untouched. `LLMClient._build_prompt` formats it as `"<tool> on turn N: <reason>"` or `"(none)"` and replaces `{{LAST_MISTAKE}}`.

**Feature D — Recent Calls**: `AgentState` gains `recent_calls: list = []`. After every `ToolDispatcher.dispatch` call in `GameLoop._run_agent_turn`, the call is appended as `{"tool_name", "arguments", "turn_number"}` and the list is trimmed to the last 5 entries. Parse errors (no dispatch) are not recorded. `LLMClient._build_prompt` formats each entry as `"turn N: tool(args)"` or `"(none)"` and replaces `{{RECENT_CALLS}}`.

**Feature B — Last Known Location**: `AgentState` gains `last_known_position` and `last_known_position_turn` (both default `None`). `ToolDispatcher._check_coordinates` sets them on success using `agent.position` and `world.turn_number`. `LLMClient._build_prompt` formats the value as `"(x, y) confirmed on turn N"` or `"(unknown)"` and replaces `{{LAST_KNOWN_LOCATION}}`. The prompt template has a **Last confirmed location** section in the **Your Current State** block.

## Key Files
- `src/agents/state.py`
  - `AgentState.last_known_position: tuple[int,int] | None`
  - `AgentState.last_known_position_turn: int | None`
  - `AgentState.last_mistake: dict | None`
  - `AgentState.recent_calls: list`
- `src/agents/tools.py`
  - `_check_coordinates(args, agent, world)` — sets both location fields on success
- `src/agents/llm_client.py`
  - `LLMClient._build_prompt(agent, world)` — injects `{{LAST_KNOWN_LOCATION}}`, `{{LAST_MISTAKE}}`, `{{RECENT_CALLS}}`
- `src/loop/game_loop.py`
  - `GameLoop._run_agent_turn` — records `last_mistake` on parse error and tool failure; appends to `recent_calls` after every dispatch
- `prompts/agent_system.md` — added `{{LAST_KNOWN_LOCATION}}`, `{{LAST_MISTAKE}}`, `{{RECENT_CALLS}}` sections

## Testing
- **Unit (Feature B)** — `_check_coordinates` sets `last_known_position` and `last_known_position_turn`; other tools leave them `None`; `_build_prompt` injects `"(x, y) confirmed on turn N"` when set, `"(unknown)"` otherwise; second call overwrites both fields
- **Unit (Feature C)** — tool failure sets `last_mistake` with correct fields; parse error sets `last_mistake` with `"(parse_error)"`; success leaves existing mistake intact; `_build_prompt` formats or returns `"(none)"`
- **Unit (Feature D)** — recent call appended after dispatch; list trimmed to 5; failed dispatches are included; `_build_prompt` formats or returns `"(none)"`
