"""Tests for src/loop/game_loop.py."""

from unittest.mock import MagicMock, call, patch

import pytest

from src.agents.state import AgentState, LLMResponse, ParseError, ToolResult
from src.loop.game_loop import EndCondition, GameLoop, RunResult
from src.world.state import CellType, WorldState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world(agent_a_pos=(0, 0), agent_b_pos=(7, 7)):
    grid = [[CellType.EMPTY] * 8 for _ in range(8)]
    grid[3][3] = CellType.KEY
    grid[6][6] = CellType.EXIT_LOCKED
    return WorldState(
        grid=grid,
        key_pos=(3, 3),
        exit_pos=(6, 6),
        agent_positions={"agent_a": agent_a_pos, "agent_b": agent_b_pos},
    )


def _make_agent(agent_id, position):
    return AgentState(agent_id=agent_id, position=position)


def _look_response():
    return LLMResponse(reasoning="looking", expected_state={}, tool_name="look", arguments={})


def _make_loop(world=None, agent_a=None, agent_b=None, llm_a=None, llm_b=None, logger=None, max_turns=50):
    if world is None:
        world = _make_world()
    if agent_a is None:
        agent_a = _make_agent("agent_a", world.agent_positions["agent_a"])
    if agent_b is None:
        agent_b = _make_agent("agent_b", world.agent_positions["agent_b"])
    if llm_a is None:
        llm_a = MagicMock()
        llm_a.get_decision.return_value = _look_response()
    if llm_b is None:
        llm_b = MagicMock()
        llm_b.get_decision.return_value = _look_response()
    if logger is None:
        logger = MagicMock()
    return GameLoop(world, agent_a, agent_b, llm_a, llm_b, logger, max_turns=max_turns)


# ---------------------------------------------------------------------------
# EndCondition / RunResult types
# ---------------------------------------------------------------------------

def test_end_condition_members():
    members = {e.name for e in EndCondition}
    assert members == {"SUCCESS", "TURN_LIMIT", "ACTION_DEADLOCK", "PARSE_DEADLOCK"}


def test_run_result_fields():
    r = RunResult(end_condition=EndCondition.TURN_LIMIT, turn_number=50, log_path=None)
    assert r.end_condition == EndCondition.TURN_LIMIT
    assert r.turn_number == 50
    assert r.log_path is None


# ---------------------------------------------------------------------------
# _deliver_messages
# ---------------------------------------------------------------------------

def test_deliver_messages_moves_partner_outbox_to_agent_inbox():
    world = _make_world()
    agent_a = _make_agent("agent_a", (0, 0))
    agent_b = _make_agent("agent_b", (7, 7))
    agent_b.message_outbox = ["hello from B"]

    loop = _make_loop(world=world, agent_a=agent_a, agent_b=agent_b)
    loop._deliver_messages(agent_a, agent_b)

    assert agent_a.message_inbox == ["hello from B"]
    assert agent_b.message_outbox == []


def test_deliver_messages_clears_partner_outbox():
    world = _make_world()
    agent_a = _make_agent("agent_a", (0, 0))
    agent_b = _make_agent("agent_b", (7, 7))
    agent_b.message_outbox = ["msg1", "msg2"]

    loop = _make_loop(world=world, agent_a=agent_a, agent_b=agent_b)
    loop._deliver_messages(agent_a, agent_b)

    assert agent_b.message_outbox == []


def test_message_sent_by_agent_a_not_received_in_same_round():
    """Agent A sends on turn N; Agent B should NOT see it until turn N+1."""
    world = _make_world()
    agent_a = _make_agent("agent_a", (0, 0))
    agent_b = _make_agent("agent_b", (7, 7))

    send_response = LLMResponse(
        reasoning="sending", expected_state={}, tool_name="send_message",
        arguments={"agent": "agent_b", "message": "meet at exit"},
    )
    look_response = _look_response()

    llm_a = MagicMock()
    llm_b = MagicMock()

    # Round 0: A sends, B does look (B should NOT see message yet)
    # Round 1: A does look, B does look (B SHOULD see message now)
    llm_a.get_decision.side_effect = [send_response, look_response]
    llm_b.get_decision.side_effect = [look_response, look_response]

    b_inbox_snapshots = []
    b_responses = [look_response, look_response]
    b_call_count = [0]

    def capture_b_inbox(agent, world):
        b_inbox_snapshots.append(list(agent.message_inbox))
        resp = b_responses[b_call_count[0]]
        b_call_count[0] += 1
        return resp

    llm_b.get_decision.side_effect = capture_b_inbox

    loop = _make_loop(world=world, agent_a=agent_a, agent_b=agent_b,
                      llm_a=llm_a, llm_b=llm_b, max_turns=2)
    loop.run()

    # During round 0 (index 0): B inbox should be empty
    assert b_inbox_snapshots[0] == []
    # During round 1 (index 1): B inbox should have A's message
    assert "meet at exit" in b_inbox_snapshots[1]


# ---------------------------------------------------------------------------
# _check_success
# ---------------------------------------------------------------------------

def test_check_success_true_when_both_at_exit_and_unlocked():
    world = _make_world(agent_a_pos=(6, 6), agent_b_pos=(6, 6))
    world.exit_locked = False
    world.grid[6][6] = CellType.EXIT_UNLOCKED
    loop = _make_loop(world=world)
    assert loop._check_success() is True


def test_check_success_false_when_exit_locked():
    world = _make_world(agent_a_pos=(6, 6), agent_b_pos=(6, 6))
    # exit_locked stays True
    loop = _make_loop(world=world)
    assert loop._check_success() is False


def test_check_success_false_when_only_one_agent_at_exit():
    world = _make_world(agent_a_pos=(6, 6), agent_b_pos=(0, 0))
    world.exit_locked = False
    world.grid[6][6] = CellType.EXIT_UNLOCKED
    loop = _make_loop(world=world)
    assert loop._check_success() is False


# ---------------------------------------------------------------------------
# End conditions
# ---------------------------------------------------------------------------

def test_turn_limit_ends_game():
    loop = _make_loop(max_turns=2)
    result = loop.run()
    assert result.end_condition == EndCondition.TURN_LIMIT
    assert result.turn_number == 2


def test_action_deadlock_ends_game():
    world = _make_world()
    agent_a = _make_agent("agent_a", (0, 0))
    agent_b = _make_agent("agent_b", (7, 7))

    # Agent A always tries to move north (out of bounds — failure)
    fail_response = LLMResponse(
        reasoning="moving", expected_state={}, tool_name="move",
        arguments={"direction": "north"},
    )
    llm_a = MagicMock()
    llm_a.get_decision.return_value = fail_response
    llm_b = MagicMock()
    llm_b.get_decision.return_value = _look_response()

    loop = _make_loop(world=world, agent_a=agent_a, agent_b=agent_b,
                      llm_a=llm_a, llm_b=llm_b)
    result = loop.run()

    assert result.end_condition == EndCondition.ACTION_DEADLOCK


def test_parse_deadlock_ends_game():
    world = _make_world()
    agent_a = _make_agent("agent_a", (0, 0))
    agent_b = _make_agent("agent_b", (7, 7))

    def raise_parse_error(agent, world):
        # mirrors LLMClient behaviour: increment before raising
        agent.consecutive_parse_failures += 1
        raise ParseError("bad json")

    llm_a = MagicMock()
    llm_a.get_decision.side_effect = raise_parse_error
    llm_b = MagicMock()
    llm_b.get_decision.return_value = _look_response()

    loop = _make_loop(world=world, agent_a=agent_a, agent_b=agent_b,
                      llm_a=llm_a, llm_b=llm_b)

    # Pre-set to 2 so the 3rd failure (first in this run) hits the threshold
    agent_a.consecutive_parse_failures = 2
    result = loop.run()

    assert result.end_condition == EndCondition.PARSE_DEADLOCK


def test_success_ends_game():
    # Both agents start at exit, exit is unlocked
    world = _make_world(agent_a_pos=(6, 6), agent_b_pos=(6, 6))
    world.exit_locked = False
    world.grid[6][6] = CellType.EXIT_UNLOCKED

    loop = _make_loop(world=world)
    result = loop.run()

    assert result.end_condition == EndCondition.SUCCESS


# ---------------------------------------------------------------------------
# Turn order: Agent A acts before Agent B in every round
# ---------------------------------------------------------------------------

def test_turn_order_agent_a_acts_before_agent_b():
    call_order = []

    llm_a = MagicMock()
    llm_b = MagicMock()

    def a_decision(agent, world):
        call_order.append("agent_a")
        return _look_response()

    def b_decision(agent, world):
        call_order.append("agent_b")
        return _look_response()

    llm_a.get_decision.side_effect = a_decision
    llm_b.get_decision.side_effect = b_decision

    loop = _make_loop(llm_a=llm_a, llm_b=llm_b, max_turns=2)
    loop.run()

    # Every pair should be A then B
    for i in range(0, len(call_order) - 1, 2):
        assert call_order[i] == "agent_a"
        assert call_order[i + 1] == "agent_b"


# ---------------------------------------------------------------------------
# Logger is called once per agent action
# ---------------------------------------------------------------------------

def test_logger_called_for_each_action():
    logger = MagicMock()
    loop = _make_loop(logger=logger, max_turns=2)
    loop.run()
    # 2 turns × 2 agents = 4 log_event calls
    assert logger.log_event.call_count == 4


# ---------------------------------------------------------------------------
# turn_number increments after each full round
# ---------------------------------------------------------------------------

def test_turn_number_increments_each_round():
    world = _make_world()
    loop = _make_loop(world=world, max_turns=3)
    loop.run()
    assert world.turn_number == 3
