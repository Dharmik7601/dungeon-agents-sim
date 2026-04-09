"""Tests for src/agents/state.py, src/agents/tools.py, src/agents/llm_client.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.state import AgentState, LLMResponse, ParseError, ToolResult
from src.agents.tools import ToolDispatcher
from src.agents.llm_client import LLMClient
from src.world.state import CellType, WorldState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world():
    """8x8 open grid with key at (3,3), exit at (6,6), agents at (0,0) and (7,7)."""
    grid = [[CellType.EMPTY] * 8 for _ in range(8)]
    grid[3][3] = CellType.KEY
    grid[6][6] = CellType.EXIT_LOCKED
    return WorldState(
        grid=grid,
        key_pos=(3, 3),
        exit_pos=(6, 6),
        agent_positions={"agent_a": (0, 0), "agent_b": (7, 7)},
    )


def _make_agent(agent_id="agent_a", position=(0, 0)):
    return AgentState(agent_id=agent_id, position=position)


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

def test_agentstate_defaults():
    a = AgentState(agent_id="agent_a", position=(0, 0))
    assert a.inventory == []
    assert a.shadow_map == {}
    assert a.message_inbox == []
    assert a.message_outbox == []
    assert a.consecutive_invalid_actions == 0
    assert a.consecutive_parse_failures == 0


# ---------------------------------------------------------------------------
# ToolResult / LLMResponse / ParseError
# ---------------------------------------------------------------------------

def test_toolresult_fields():
    r = ToolResult(status="success", message="ok", data={})
    assert r.status == "success"


def test_llmresponse_fields():
    r = LLMResponse(reasoning="r", expected_state={}, tool_name="look", arguments={})
    assert r.tool_name == "look"


def test_parseerror_is_exception():
    with pytest.raises(ParseError):
        raise ParseError("bad json")


# ---------------------------------------------------------------------------
# ToolDispatcher — move
# ---------------------------------------------------------------------------

def test_move_success_updates_position():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch("move", {"direction": "south"}, agent, ws)
    assert result.status == "success"
    assert agent.position == (0, 1)
    assert ws.agent_positions["agent_a"] == (0, 1)


def test_move_into_wall_returns_failure():
    ws = _make_world()
    ws.grid[0][1] = CellType.WALL   # cell to the east of (0,0)
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch("move", {"direction": "east"}, agent, ws)
    assert result.status == "failure"
    assert agent.position == (0, 0)
    assert ws.agent_positions["agent_a"] == (0, 0)


def test_move_out_of_bounds_returns_failure():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch("move", {"direction": "north"}, agent, ws)
    assert result.status == "failure"
    assert agent.position == (0, 0)


def test_move_success_resets_invalid_action_counter():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    agent.consecutive_invalid_actions = 3
    ToolDispatcher.dispatch("move", {"direction": "east"}, agent, ws)
    assert agent.consecutive_invalid_actions == 0


def test_move_failure_increments_invalid_action_counter():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    ToolDispatcher.dispatch("move", {"direction": "north"}, agent, ws)
    assert agent.consecutive_invalid_actions == 1


def test_move_updates_shadow_map_on_success():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    ToolDispatcher.dispatch("move", {"direction": "east"}, agent, ws)
    assert (1, 0) in agent.shadow_map


# ---------------------------------------------------------------------------
# ToolDispatcher — look
# ---------------------------------------------------------------------------

def test_look_reveals_current_and_adjacent_cells():
    ws = _make_world()
    agent = _make_agent("agent_a", (1, 1))
    ToolDispatcher.dispatch("look", {}, agent, ws)
    for pos in [(1, 1), (1, 0), (1, 2), (0, 1), (2, 1)]:
        assert pos in agent.shadow_map, f"{pos} not in shadow_map after look"


def test_look_does_not_reveal_out_of_bounds():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    ToolDispatcher.dispatch("look", {}, agent, ws)
    assert (-1, 0) not in agent.shadow_map
    assert (0, -1) not in agent.shadow_map


def test_look_does_not_update_other_agent_shadow_map():
    ws = _make_world()
    agent_a = _make_agent("agent_a", (1, 1))
    agent_b = _make_agent("agent_b", (7, 7))
    ToolDispatcher.dispatch("look", {}, agent_a, ws)
    assert len(agent_b.shadow_map) == 0


# ---------------------------------------------------------------------------
# ToolDispatcher — pick_up
# ---------------------------------------------------------------------------

def test_pick_up_success_adds_to_inventory_and_clears_cell():
    ws = _make_world()
    agent = _make_agent("agent_a", (3, 3))
    result = ToolDispatcher.dispatch("pick_up", {"item": "key"}, agent, ws)
    assert result.status == "success"
    assert "key" in agent.inventory
    assert ws.grid[3][3] == CellType.EMPTY
    assert ws.key_pos is None


def test_pick_up_wrong_cell_returns_failure():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch("pick_up", {"item": "key"}, agent, ws)
    assert result.status == "failure"
    assert agent.inventory == []


def test_pick_up_updates_shadow_map():
    ws = _make_world()
    agent = _make_agent("agent_a", (3, 3))
    ToolDispatcher.dispatch("pick_up", {"item": "key"}, agent, ws)
    assert agent.shadow_map[(3, 3)] == CellType.EMPTY


# ---------------------------------------------------------------------------
# ToolDispatcher — check_coordinates
# ---------------------------------------------------------------------------

def test_check_coordinates_returns_position():
    ws = _make_world()
    agent = _make_agent("agent_a", (2, 4))
    result = ToolDispatcher.dispatch("check_coordinates", {}, agent, ws)
    assert result.status == "success"
    assert result.data["position"] == (2, 4)


def test_check_coordinates_does_not_mutate_world():
    ws = _make_world()
    agent = _make_agent("agent_a", (2, 4))
    before = ws.agent_positions.copy()
    ToolDispatcher.dispatch("check_coordinates", {}, agent, ws)
    assert ws.agent_positions == before


# ---------------------------------------------------------------------------
# ToolDispatcher — check_inventory
# ---------------------------------------------------------------------------

def test_check_inventory_returns_current_items():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    agent.inventory = ["key"]
    result = ToolDispatcher.dispatch("check_inventory", {}, agent, ws)
    assert result.status == "success"
    assert result.data["inventory"] == ["key"]


# ---------------------------------------------------------------------------
# ToolDispatcher — use_item
# ---------------------------------------------------------------------------

def test_use_item_unlocks_exit_when_key_in_inventory_and_adjacent():
    ws = _make_world()
    agent = _make_agent("agent_a", (6, 5))   # one cell north of exit (6,6)
    agent.inventory = ["key"]
    result = ToolDispatcher.dispatch("use_item", {"item": "key", "target": "exit"}, agent, ws)
    assert result.status == "success"
    assert ws.exit_locked is False
    assert ws.grid[6][6] == CellType.EXIT_UNLOCKED


def test_use_item_fails_without_key_in_inventory():
    ws = _make_world()
    agent = _make_agent("agent_a", (6, 5))
    result = ToolDispatcher.dispatch("use_item", {"item": "key", "target": "exit"}, agent, ws)
    assert result.status == "failure"
    assert ws.exit_locked is True


def test_use_item_fails_when_not_adjacent_to_exit():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    agent.inventory = ["key"]
    result = ToolDispatcher.dispatch("use_item", {"item": "key", "target": "exit"}, agent, ws)
    assert result.status == "failure"
    assert ws.exit_locked is True


def test_use_item_updates_shadow_map_on_success():
    ws = _make_world()
    agent = _make_agent("agent_a", (6, 5))
    agent.inventory = ["key"]
    ToolDispatcher.dispatch("use_item", {"item": "key", "target": "exit"}, agent, ws)
    assert agent.shadow_map[(6, 6)] == CellType.EXIT_UNLOCKED


# ---------------------------------------------------------------------------
# ToolDispatcher — send_message
# ---------------------------------------------------------------------------

def test_send_message_places_in_outbox():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch(
        "send_message", {"agent": "agent_b", "message": "I have the key"}, agent, ws
    )
    assert result.status == "success"
    assert "I have the key" in agent.message_outbox
    assert agent.message_inbox == []


# ---------------------------------------------------------------------------
# ToolDispatcher — unknown tool
# ---------------------------------------------------------------------------

def test_unknown_tool_returns_failure():
    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))
    result = ToolDispatcher.dispatch("teleport", {"x": 5, "y": 5}, agent, ws)
    assert result.status == "failure"
    assert agent.consecutive_invalid_actions == 1


# ---------------------------------------------------------------------------
# Shadow state isolation between agents
# ---------------------------------------------------------------------------

def test_agent_a_pickup_does_not_update_agent_b_shadow_map():
    ws = _make_world()
    agent_a = _make_agent("agent_a", (3, 3))
    agent_b = _make_agent("agent_b", (7, 7))
    ToolDispatcher.dispatch("pick_up", {"item": "key"}, agent_a, ws)
    # agent_b's shadow map should still be empty
    assert (3, 3) not in agent_b.shadow_map


# ---------------------------------------------------------------------------
# LLMClient — prompt injection and JSON parsing
# ---------------------------------------------------------------------------

def _make_llm_client(tmp_path, content="<system_prompt>{{AGENT_ID}}{{TURN_NUMBER}}{{SHADOW_MAP}}{{INVENTORY}}{{MESSAGES}}</system_prompt>"):
    prompt_file = tmp_path / "agent_system.md"
    prompt_file.write_text(content)
    with patch("src.agents.llm_client.genai") as mock_genai:
        mock_genai.Client.return_value = MagicMock()
        client = LLMClient(model_name="gemma-3-27b-it", prompt_path=str(prompt_file))
    client._mock_genai_client = mock_genai  # not used after init; tests patch at call time
    return client, str(prompt_file)


def test_llmclient_injects_all_placeholders(tmp_path):
    prompt_content = (
        "<system_prompt>\n"
        "Agent: {{AGENT_ID}} Turn: {{TURN_NUMBER}}\n"
        "Map: {{SHADOW_MAP}}\n"
        "Inventory: {{INVENTORY}}\n"
        "Messages: {{MESSAGES}}\n"
        "</system_prompt>"
    )
    prompt_file = tmp_path / "agent_system.md"
    prompt_file.write_text(prompt_content)

    valid_response_text = json.dumps({
        "reasoning": "moving east",
        "expected_state": {},
        "tool_name": "move",
        "arguments": {"direction": "east"},
    })
    mock_response = MagicMock()
    mock_response.text = valid_response_text

    ws = _make_world()
    ws.turn_number = 5
    agent = _make_agent("agent_a", (0, 0))
    agent.message_inbox = ["hello"]

    with patch("src.agents.llm_client.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        llm = LLMClient(model_name="gemma-3-27b-it", prompt_path=str(prompt_file))
        result = llm.get_decision(agent, ws)

        call_kwargs = mock_client.models.generate_content.call_args[1]
        prompt_sent = call_kwargs["contents"]

    assert "agent_a" in prompt_sent
    assert "5" in prompt_sent
    assert "hello" in prompt_sent
    assert "{{AGENT_ID}}" not in prompt_sent
    assert "{{TURN_NUMBER}}" not in prompt_sent
    assert "{{SHADOW_MAP}}" not in prompt_sent
    assert "{{INVENTORY}}" not in prompt_sent
    assert "{{MESSAGES}}" not in prompt_sent
    assert result.tool_name == "move"
    assert result.reasoning == "moving east"


def test_llmclient_parses_json_response(tmp_path):
    prompt_file = tmp_path / "agent_system.md"
    prompt_file.write_text("<system_prompt>{{AGENT_ID}}{{TURN_NUMBER}}{{SHADOW_MAP}}{{INVENTORY}}{{MESSAGES}}</system_prompt>")

    valid_response = json.dumps({
        "reasoning": "exploring",
        "expected_state": {"cell_status_1_0": "empty"},
        "tool_name": "look",
        "arguments": {},
    })
    mock_response = MagicMock()
    mock_response.text = valid_response

    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))

    with patch("src.agents.llm_client.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response
        llm = LLMClient(model_name="gemma-3-27b-it", prompt_path=str(prompt_file))
        result = llm.get_decision(agent, ws)

    assert result.tool_name == "look"
    assert result.expected_state == {"cell_status_1_0": "empty"}


def test_llmclient_increments_parse_failures_on_bad_json(tmp_path):
    prompt_file = tmp_path / "agent_system.md"
    prompt_file.write_text("<system_prompt>{{AGENT_ID}}{{TURN_NUMBER}}{{SHADOW_MAP}}{{INVENTORY}}{{MESSAGES}}</system_prompt>")

    mock_response = MagicMock()
    mock_response.text = "this is not json at all"

    ws = _make_world()
    agent = _make_agent("agent_a", (0, 0))

    with patch("src.agents.llm_client.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response
        llm = LLMClient(model_name="gemma-3-27b-it", prompt_path=str(prompt_file))
        with pytest.raises(ParseError):
            llm.get_decision(agent, ws)

    assert agent.consecutive_parse_failures == 1
