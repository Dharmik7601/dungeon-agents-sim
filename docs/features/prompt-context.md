# Prompt Context Enrichment

## What It Does
Tracks three per-agent context fields that are injected into every LLM prompt:

1. **Last Known Location** — the position and turn number confirmed by the most recent `check_coordinates()` call. Remains stale until the tool is called again.
2. **Last Mistake** — the most recent failed tool call (tool name, turn, reason). Persists across turns until a new mistake replaces it.
3. **Recent Calls** — a sliding window of the 5 most recently dispatched tool calls (tool name, arguments, turn number), updated after every dispatch.

## Implementation

**Feature B — Last Known Location**: `AgentState` gains `last_known_position` and `last_known_position_turn` (both default `None`). `ToolDispatcher._check_coordinates` sets them on success using `agent.position` and `world.turn_number`. `LLMClient._build_prompt` formats the value as `"(x, y) confirmed on turn N"` or `"(unknown)"` and replaces `{{LAST_KNOWN_LOCATION}}`. The prompt template has a **Last confirmed location** section in the **Your Current State** block.

## Key Files
- `src/agents/state.py`
  - `AgentState.last_known_position: tuple[int,int] | None`
  - `AgentState.last_known_position_turn: int | None`
- `src/agents/tools.py`
  - `_check_coordinates(args, agent, world)` — sets both location fields on success
- `src/agents/llm_client.py`
  - `LLMClient._build_prompt(agent, world)` — injects `{{LAST_KNOWN_LOCATION}}`
- `prompts/agent_system.md` — added `{{LAST_KNOWN_LOCATION}}` section

## Testing
- **Unit** — `_check_coordinates` sets `last_known_position` and `last_known_position_turn`; `look` and other tools leave them `None`; `_build_prompt` injects `"(x, y) confirmed on turn N"` when set; injects `"(unknown)"` when `None`
- **Edge cases** — calling `check_coordinates()` twice overwrites both fields with the latest values
