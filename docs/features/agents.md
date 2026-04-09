# Agents

## What It Does
Manages the per-agent belief state (shadow map, inventory, message queues, deadlock counters), executes validated tool calls against ground truth, and drives the LLM API call with prompt injection and structured JSON response parsing. This feature is the enforcement point for the three-layer state invariant: shadow state is updated only as an explicit side-effect of a tool call, never passively.

## Implementation

**`src/agents/state.py`** — four types:
- `AgentState` (dataclass): `agent_id`, `position`, `inventory`, `shadow_map`, `message_inbox`, `message_outbox`, `consecutive_invalid_actions`, `consecutive_parse_failures`.
- `ToolResult` (dataclass): `status` ("success"|"failure"), `message`, `data`.
- `LLMResponse` (dataclass): `reasoning`, `expected_state`, `tool_name`, `arguments`.
- `ParseError(Exception)`: raised when the LLM returns non-parseable JSON.

**`src/agents/tools.py`** — `ToolDispatcher.dispatch(tool_name, arguments, agent, world) -> ToolResult`. Routes to one of 7 private handler functions. Each handler validates against ground truth before mutating anything. On failure: increments `consecutive_invalid_actions`, returns `ToolResult(status="failure")` without touching `WorldState`. On success: resets `consecutive_invalid_actions` to 0, updates `WorldState` and the calling agent's `shadow_map` only.

**`src/agents/llm_client.py`** — `LLMClient(model_name, prompt_path)`. On `get_decision(agent, world)`: reads the XML prompt template, replaces all 5 `{{PLACEHOLDER}}` tokens with runtime values, calls `genai.Client().models.generate_content(model=..., contents=...)`, strips any markdown fences from the response, parses JSON into `LLMResponse`. On `json.JSONDecodeError`: increments `agent.consecutive_parse_failures` and raises `ParseError`. Uses `google-genai` SDK (not the deprecated `google-generativeai`); API key is read from `GOOGLE_API_KEY` env var automatically by the SDK.

## Key Files
- `src/agents/state.py`
  - `AgentState` (dataclass) — per-agent mutable state, 8 fields
  - `ToolResult` (dataclass) — `status`, `message`, `data`
  - `LLMResponse` (dataclass) — `reasoning`, `expected_state`, `tool_name`, `arguments`
  - `ParseError(Exception)` — raised on unparseable LLM JSON
- `src/agents/tools.py`
  - `ToolDispatcher.dispatch(tool_name, arguments, agent, world) -> ToolResult`
- `src/agents/llm_client.py`
  - `LLMClient.__init__(model_name, prompt_path)` — loads prompt template, creates SDK client
  - `LLMClient.get_decision(agent, world) -> LLMResponse` — builds prompt, calls API, parses response

## Testing
- **Unit** — `AgentState` field defaults; `ToolResult`/`LLMResponse`/`ParseError` types; all 7 tool handlers (success path mutates correct state, failure path returns status="failure" without mutation); deadlock counter increments/resets; `LLMClient` prompt injection replaces all 5 tokens; JSON parsing extracts all 4 fields; `ParseError` raised and counter incremented on bad JSON
- **Integration** — Agent A `pick_up` leaves Agent B shadow map stale; `move` into wall returns failure, position unchanged; `look` reveals all adjacent cells
- **Edge cases** — unknown tool name returns failure; `pick_up` on empty cell fails; `use_item` without key fails; `use_item` not adjacent to exit fails; out-of-bounds move fails
