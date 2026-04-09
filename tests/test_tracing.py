"""Tests for src/tracing/semantic_logger.py and src/tracing/langfuse_wrapper.py."""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.state import AgentState, LLMResponse, ToolResult
from src.tracing.semantic_logger import SemanticLogger, _compute_deltas, _ground_truth_snapshot
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


def _make_agent(agent_id="agent_a", position=(0, 0)):
    return AgentState(agent_id=agent_id, position=position)


def _look_llm(expected_state=None):
    return LLMResponse(
        reasoning="looking around",
        expected_state=expected_state or {},
        tool_name="look",
        arguments={},
    )


def _move_llm(direction="east", expected_state=None):
    return LLMResponse(
        reasoning=f"moving {direction}",
        expected_state=expected_state or {},
        tool_name="move",
        arguments={"direction": direction},
    )


def _success_result(message="ok", data=None):
    return ToolResult(status="success", message=message, data=data or {})


def _failure_result(message="failed"):
    return ToolResult(status="failure", message=message)


# ---------------------------------------------------------------------------
# _ground_truth_snapshot
# ---------------------------------------------------------------------------

def test_ground_truth_snapshot_includes_cell_statuses():
    world = _make_world()
    snapshot = _ground_truth_snapshot(world)
    # Key cell
    assert snapshot.get("cell_status_3_3") == "key"
    # Exit cell
    assert snapshot.get("cell_status_6_6") == "exit_locked"
    # Empty cell
    assert snapshot.get("cell_status_0_0") == "empty"


def test_ground_truth_snapshot_includes_agent_positions():
    world = _make_world(agent_a_pos=(2, 3))
    snapshot = _ground_truth_snapshot(world)
    assert snapshot.get("agent_a_position") == [2, 3]
    assert snapshot.get("agent_b_position") == [7, 7]


# ---------------------------------------------------------------------------
# _compute_deltas
# ---------------------------------------------------------------------------

def test_compute_deltas_move_no_mismatch():
    world = _make_world()
    # Agent at (0,0) expects (1,0) to be empty — it is empty
    expected = {"cell_status_1_0": "empty"}
    shadow_before = {(1, 0): CellType.EMPTY}
    deltas = _compute_deltas("move", expected, shadow_before, world, agent_pos=(0, 0))
    assert deltas == []


def test_compute_deltas_move_wall_mismatch():
    world = _make_world()
    world.grid[0][1] = CellType.WALL
    # Agent expected (1,0) to be empty but it's a wall
    expected = {"cell_status_1_0": "empty"}
    shadow_before = {(1, 0): CellType.EMPTY}   # shadow was stale
    deltas = _compute_deltas("move", expected, shadow_before, world, agent_pos=(0, 0))
    assert len(deltas) == 1
    assert deltas[0]["property_key"] == "cell_status_1_0"
    assert deltas[0]["expected_value"] == "empty"
    assert deltas[0]["actual_value"] == "wall"
    assert deltas[0]["discrepancy_source"] == "stale_shadow_state"


def test_compute_deltas_move_fog_of_war():
    world = _make_world()
    world.grid[0][1] = CellType.WALL
    expected = {"cell_status_1_0": "empty"}
    shadow_before = {}   # cell never observed
    deltas = _compute_deltas("move", expected, shadow_before, world, agent_pos=(0, 0))
    assert len(deltas) == 1
    assert deltas[0]["discrepancy_source"] == "fog_of_war"


def test_compute_deltas_pick_up_mismatch():
    world = _make_world()
    world.grid[3][3] = CellType.EMPTY   # key already gone (partner took it)
    world.key_pos = None
    # Agent expected key at (3,3) but cell is empty
    expected = {"cell_contents_3_3": ["key"]}
    shadow_before = {(3, 3): CellType.KEY}   # shadow was stale
    deltas = _compute_deltas("pick_up", expected, shadow_before, world, agent_pos=(3, 3))
    assert len(deltas) == 1
    assert deltas[0]["property_key"] == "cell_contents_3_3"
    assert deltas[0]["discrepancy_source"] == "stale_shadow_state"


def test_compute_deltas_look_produces_no_deltas():
    world = _make_world()
    deltas = _compute_deltas("look", {}, {}, world, agent_pos=(0, 0))
    assert deltas == []


def test_compute_deltas_send_message_produces_no_deltas():
    world = _make_world()
    deltas = _compute_deltas("send_message", {}, {}, world, agent_pos=(0, 0))
    assert deltas == []


def test_compute_deltas_check_inventory_produces_no_deltas():
    world = _make_world()
    deltas = _compute_deltas("check_inventory", {}, {}, world, agent_pos=(0, 0))
    assert deltas == []


def test_compute_deltas_use_item_inventory_mismatch():
    world = _make_world()
    # Agent expected to have key but inventory is empty
    expected = {"agent_inventory": ["key"]}
    shadow_before = {}
    deltas = _compute_deltas("use_item", expected, shadow_before, world, agent_pos=(5, 6))
    assert any(d["property_key"] == "agent_inventory" for d in deltas)


# ---------------------------------------------------------------------------
# SemanticLogger.log_event — schema shape
# ---------------------------------------------------------------------------

def test_log_event_produces_event_with_required_keys():
    logger = SemanticLogger()
    world = _make_world()
    agent = _make_agent("agent_a", (0, 0))

    logger.log_event(
        turn_number=1,
        agent_id="agent_a",
        llm_response=_look_llm(),
        shadow_state_before={},
        tool_result=_success_result(),
        world=world,
    )

    assert len(logger._events) == 1
    event = logger._events[0]
    for key in ("event_id", "timestamp", "turn_number", "agent_id", "action",
                "state_context", "execution_result"):
        assert key in event, f"Missing key: {key}"


def test_log_event_action_contains_tool_and_args():
    logger = SemanticLogger()
    world = _make_world()
    response = _move_llm("north")

    logger.log_event(
        turn_number=0,
        agent_id="agent_a",
        llm_response=response,
        shadow_state_before={},
        tool_result=_success_result(),
        world=world,
    )

    action = logger._events[0]["action"]
    assert action["tool_name"] == "move"
    assert action["arguments"] == {"direction": "north"}


def test_log_event_state_context_has_three_layers():
    logger = SemanticLogger()
    world = _make_world()
    shadow = {(0, 1): CellType.EMPTY}

    logger.log_event(
        turn_number=0,
        agent_id="agent_a",
        llm_response=_look_llm({"cell_status_0_1": "empty"}),
        shadow_state_before=shadow,
        tool_result=_success_result(),
        world=world,
    )

    ctx = logger._events[0]["state_context"]
    assert "agent_beliefs" in ctx
    assert "shadow_state" in ctx
    assert "ground_truth" in ctx
    assert ctx["agent_beliefs"]["reasoning"] == "looking around"


def test_log_event_execution_result_success():
    logger = SemanticLogger()
    world = _make_world()

    logger.log_event(
        turn_number=0,
        agent_id="agent_a",
        llm_response=_look_llm(),
        shadow_state_before={},
        tool_result=_success_result("Moved east"),
        world=world,
    )

    result = logger._events[0]["execution_result"]
    assert result["status"] == "success"
    assert result["error_message"] is None
    assert result["deltas"] == []


def test_log_event_execution_result_failure():
    logger = SemanticLogger()
    world = _make_world()

    logger.log_event(
        turn_number=0,
        agent_id="agent_a",
        llm_response=_move_llm("north", {"cell_status_0_-1": "empty"}),
        shadow_state_before={},
        tool_result=_failure_result("Cannot move north: out of bounds"),
        world=world,
    )

    result = logger._events[0]["execution_result"]
    assert result["status"] == "failure"
    assert result["error_message"] == "Cannot move north: out of bounds"


# ---------------------------------------------------------------------------
# SemanticLogger.flush
# ---------------------------------------------------------------------------

def test_flush_writes_valid_json_array(tmp_path):
    logger = SemanticLogger(data_dir=str(tmp_path))
    world = _make_world()

    for _ in range(2):
        logger.log_event(
            turn_number=0,
            agent_id="agent_a",
            llm_response=_look_llm(),
            shadow_state_before={},
            tool_result=_success_result(),
            world=world,
        )

    path = logger.flush(run_id="test01")
    assert path is not None
    content = json.loads(Path(path).read_text())
    assert isinstance(content, list)
    assert len(content) == 2


def test_flush_creates_data_dir_if_missing(tmp_path):
    data_dir = tmp_path / "new_data_dir"
    logger = SemanticLogger(data_dir=str(data_dir))
    world = _make_world()
    logger.log_event(
        turn_number=0, agent_id="agent_a",
        llm_response=_look_llm(), shadow_state_before={},
        tool_result=_success_result(), world=world,
    )
    logger.flush(run_id="x")
    assert data_dir.exists()


def test_flush_empty_events_writes_empty_array(tmp_path):
    logger = SemanticLogger(data_dir=str(tmp_path))
    path = logger.flush(run_id="empty")
    content = json.loads(Path(path).read_text())
    assert content == []


def test_flush_event_id_is_unique():
    logger = SemanticLogger()
    world = _make_world()
    for _ in range(3):
        logger.log_event(
            turn_number=0, agent_id="agent_a",
            llm_response=_look_llm(), shadow_state_before={},
            tool_result=_success_result(), world=world,
        )
    ids = [e["event_id"] for e in logger._events]
    assert len(set(ids)) == 3


# ---------------------------------------------------------------------------
# SemanticLogger — crash survival (WIP file)
# ---------------------------------------------------------------------------

def test_wip_file_written_after_each_log_event(tmp_path):
    """Events are flushed to a WIP file after every log_event call."""
    logger = SemanticLogger(data_dir=str(tmp_path))
    world = _make_world()

    logger.log_event(
        turn_number=0, agent_id="agent_a",
        llm_response=_look_llm(), shadow_state_before={},
        tool_result=_success_result(), world=world,
    )

    wip_files = list(tmp_path.glob("run_wip_*.json"))
    assert len(wip_files) == 1
    events = json.loads(wip_files[0].read_text())
    assert len(events) == 1


def test_wip_file_contains_all_events_before_flush(tmp_path):
    """WIP file grows with each event — simulates what a crash would capture."""
    logger = SemanticLogger(data_dir=str(tmp_path))
    world = _make_world()

    for _ in range(3):
        logger.log_event(
            turn_number=0, agent_id="agent_a",
            llm_response=_look_llm(), shadow_state_before={},
            tool_result=_success_result(), world=world,
        )

    # Do NOT call flush — simulate crash
    wip_files = list(tmp_path.glob("run_wip_*.json"))
    assert len(wip_files) == 1
    events = json.loads(wip_files[0].read_text())
    assert len(events) == 3


def test_wip_file_deleted_after_flush(tmp_path):
    """flush() removes the WIP file once the final file is written."""
    logger = SemanticLogger(data_dir=str(tmp_path))
    world = _make_world()

    logger.log_event(
        turn_number=0, agent_id="agent_a",
        llm_response=_look_llm(), shadow_state_before={},
        tool_result=_success_result(), world=world,
    )
    assert len(list(tmp_path.glob("run_wip_*.json"))) == 1

    logger.flush(run_id="clean_exit")

    assert len(list(tmp_path.glob("run_wip_*.json"))) == 0
    assert len(list(tmp_path.glob("run_clean_exit_*.json"))) == 1


# ---------------------------------------------------------------------------
# SemanticLogger + delta integration
# ---------------------------------------------------------------------------

def test_stale_shadow_state_appears_in_event_deltas():
    logger = SemanticLogger()
    world = _make_world()
    world.grid[0][1] = CellType.WALL   # ground truth: wall

    response = _move_llm("east", {"cell_status_1_0": "empty"})
    shadow_before = {(1, 0): CellType.EMPTY}   # stale

    logger.log_event(
        turn_number=0,
        agent_id="agent_a",
        llm_response=response,
        shadow_state_before=shadow_before,
        tool_result=_failure_result("wall"),
        world=world,
    )

    deltas = logger._events[0]["execution_result"]["deltas"]
    assert len(deltas) == 1
    assert deltas[0]["discrepancy_source"] == "stale_shadow_state"


# ---------------------------------------------------------------------------
# Langfuse wrapper — graceful fallback
# ---------------------------------------------------------------------------

def test_wrap_with_langfuse_calls_trace_and_generation(monkeypatch):
    """When Langfuse is configured, wrap_with_langfuse must call
    start_as_current_observation twice (trace span + generation) and flush —
    exercises the v4 API path so AttributeError on wrong method names is caught
    before a live run."""
    from unittest.mock import MagicMock, patch
    from src.tracing.langfuse_wrapper import wrap_with_langfuse
    import src.tracing.langfuse_wrapper as lfw

    # Simulate configured env
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    # Build mock Langfuse client for the v4 context-manager API.
    # MagicMock supports __enter__/__exit__ automatically.
    mock_lf = MagicMock()

    # Langfuse is imported inside _get_client(); patch it at the source module.
    lfw._client = None
    with patch("langfuse.Langfuse", return_value=mock_lf):
        traced = wrap_with_langfuse(
            MagicMock(**{"get_decision.return_value": LLMResponse(
                reasoning="r", expected_state={}, tool_name="look", arguments={}
            ), "_build_prompt.return_value": "prompt", "_model_name": "test-model"}),
            run_id="r1", turn_number=0, agent_id="agent_a",
        )
        result = traced(_make_agent(), _make_world())

    # Must have called start_as_current_observation twice: once for the trace
    # span and once for the generation nested inside it.
    assert mock_lf.start_as_current_observation.call_count == 2
    calls = mock_lf.start_as_current_observation.call_args_list
    assert calls[0].kwargs["name"] == "agent_turn_execution"
    assert calls[0].kwargs["as_type"] == "span"
    assert calls[1].kwargs["name"] == "get_decision"
    assert calls[1].kwargs["as_type"] == "generation"

    # The generation span (context manager entry) must have had .update() called
    # with the LLM output.
    gen_span = mock_lf.start_as_current_observation.return_value.__enter__.return_value
    gen_span.update.assert_called_once()

    mock_lf.flush.assert_called()

    # Clean up singleton so other tests are unaffected
    lfw._client = None


def test_flush_langfuse_is_noop_when_not_configured():
    """flush_langfuse() must not raise when Langfuse env vars are absent."""
    from src.tracing.langfuse_wrapper import flush_langfuse
    flush_langfuse()  # should complete silently


def test_langfuse_wrapper_falls_back_when_not_configured():
    """If Langfuse env vars are absent, the wrapper should be a no-op pass-through."""
    from src.tracing.langfuse_wrapper import wrap_with_langfuse

    mock_llm = MagicMock()
    expected_response = LLMResponse(
        reasoning="r", expected_state={}, tool_name="look", arguments={}
    )
    mock_llm.get_decision.return_value = expected_response

    world = _make_world()
    agent = _make_agent()

    wrapped = wrap_with_langfuse(mock_llm, run_id="r1", turn_number=0, agent_id="agent_a")
    result = wrapped(agent, world)

    assert result == expected_response
    mock_llm.get_decision.assert_called_once_with(agent, world)
