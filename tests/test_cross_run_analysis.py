"""Tests for src/cli/cross_run_analysis.py — all cross-run metrics."""

import json
from pathlib import Path

import pytest

from src.cli.cross_run_analysis import (
    compute_avg_exploration_density,
    compute_global_outcomes,
    compute_stubborn_failures,
    compute_tool_reliability,
    compute_top_failure_drivers,
    load_all_runs,
    main,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _event(turn, agent_id, tool="look", status="success", gt=None, deltas=None, args=None, error=None):
    return {
        "event_id": f"e{turn}{agent_id}",
        "turn_number": turn,
        "agent_id": agent_id,
        "action": {"tool_name": tool, "arguments": args or {}},
        "state_context": {
            "ground_truth": gt or {"grid_width": 8, "grid_height": 8},
            "shadow_state": {},
            "agent_input": {},
            "agent_beliefs": {"reasoning": "", "expected_state": {}},
        },
        "execution_result": {
            "status": status,
            "error_message": error,
            "deltas": deltas or [],
        },
    }


def _success_gt(x, y):
    """Both agents on unlocked exit at (x, y)."""
    return {
        "grid_width": 8,
        "grid_height": 8,
        f"cell_status_{x}_{y}": "exit_unlocked",
        "agent_a_position": [x, y],
        "agent_b_position": [x, y],
    }


def _running_gt(ex, ey):
    return {
        "grid_width": 8,
        "grid_height": 8,
        f"cell_status_{ex}_{ey}": "exit_locked",
        "agent_a_position": [0, 0],
        "agent_b_position": [1, 1],
    }


def _write_run(tmp_path, name, events):
    p = tmp_path / name
    p.write_text(json.dumps(events), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_all_runs
# ---------------------------------------------------------------------------


def test_load_all_runs_returns_list_of_event_lists(tmp_path):
    run_a = [_event(0, "agent_a"), _event(1, "agent_b")]
    run_b = [_event(0, "agent_a")]
    _write_run(tmp_path, "run_aaa.json", run_a)
    _write_run(tmp_path, "run_bbb.json", run_b)
    result = load_all_runs(tmp_path)
    assert len(result) == 2
    assert all(isinstance(r, list) for r in result)


def test_load_all_runs_exits_when_no_files_found(tmp_path):
    with pytest.raises(SystemExit):
        load_all_runs(tmp_path)


# ---------------------------------------------------------------------------
# compute_global_outcomes
# ---------------------------------------------------------------------------


def test_compute_global_outcomes_mixed_runs():
    success_run = [_event(10, "agent_b", gt=_success_gt(3, 3))]
    turn_limit_run = [_event(50, "agent_a", gt=_running_gt(7, 7))]
    other_run = [_event(13, "agent_b", gt=_running_gt(7, 7))]

    runs = [success_run, turn_limit_run, other_run]
    result = compute_global_outcomes(runs)

    assert result["total_runs"] == 3
    assert result["success_count"] == 1
    assert result["success_rate"] == pytest.approx(1 / 3 * 100)
    assert result["avg_completion_turns"] == pytest.approx(10.0)
    assert result["turn_limit_count"] == 1
    assert result["other_count"] == 1


# ---------------------------------------------------------------------------
# compute_top_failure_drivers
# ---------------------------------------------------------------------------


def test_top_failure_drivers_uses_property_key_when_deltas_present():
    delta = {"property_key": "cell_status_1_1", "expected_value": "empty",
             "actual_value": "wall", "discrepancy_source": "fog_of_war"}
    runs = [[_event(1, "agent_a", status="failure", deltas=[delta])]]
    result = compute_top_failure_drivers(runs)
    reasons = [r for r, _ in result]
    assert "cell_status_1_1" in reasons


def test_top_failure_drivers_uses_error_message_when_no_deltas():
    runs = [[_event(1, "agent_a", status="failure", error="Cannot move north: wall")]]
    result = compute_top_failure_drivers(runs)
    reasons = [r for r, _ in result]
    assert "Cannot move north: wall" in reasons


def test_top_failure_drivers_returns_at_most_five():
    events = [
        _event(i, "agent_a", status="failure", error=f"error_{i}")
        for i in range(10)
    ]
    runs = [events]
    result = compute_top_failure_drivers(runs)
    assert len(result) <= 5


def test_top_failure_drivers_sorted_by_frequency():
    # "wall_error" appears 3 times, "bounds_error" appears 1 time
    events = [
        _event(0, "agent_a", status="failure", error="wall_error"),
        _event(1, "agent_a", status="failure", error="wall_error"),
        _event(2, "agent_a", status="failure", error="wall_error"),
        _event(3, "agent_a", status="failure", error="bounds_error"),
    ]
    runs = [events]
    result = compute_top_failure_drivers(runs)
    assert result[0] == ("wall_error", 3)


# ---------------------------------------------------------------------------
# compute_stubborn_failures
# ---------------------------------------------------------------------------


def test_stubborn_failures_counts_same_action_repeat():
    # agent_a fails with move(north) twice in a row
    events = [
        _event(0, "agent_a", tool="move", status="failure", args={"direction": "north"}),
        _event(2, "agent_a", tool="move", status="failure", args={"direction": "north"}),
    ]
    result = compute_stubborn_failures([events])
    assert result["stubborn_count"] == 1
    assert result["total_failures"] == 2
    assert result["pct"] == pytest.approx(50.0)


def test_stubborn_failures_different_action_not_stubborn():
    events = [
        _event(0, "agent_a", tool="move", status="failure", args={"direction": "north"}),
        _event(2, "agent_a", tool="move", status="failure", args={"direction": "south"}),
    ]
    result = compute_stubborn_failures([events])
    assert result["stubborn_count"] == 0


def test_stubborn_failures_zero_when_no_failures():
    events = [
        _event(0, "agent_a", tool="look"),
        _event(2, "agent_a", tool="move"),
    ]
    result = compute_stubborn_failures([events])
    assert result["stubborn_count"] == 0
    assert result["total_failures"] == 0
    assert result["pct"] == 0.0


# ---------------------------------------------------------------------------
# compute_tool_reliability
# ---------------------------------------------------------------------------


def test_tool_reliability_failure_rate():
    events = [
        _event(0, "agent_a", tool="move", status="success"),
        _event(1, "agent_a", tool="move", status="failure"),
        _event(2, "agent_a", tool="look", status="success"),
    ]
    result = compute_tool_reliability([events])
    assert result["move"]["total"] == 2
    assert result["move"]["failures"] == 1
    assert result["move"]["failure_rate"] == pytest.approx(50.0)
    assert result["look"]["failure_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_avg_exploration_density
# ---------------------------------------------------------------------------


def _event_with_shadow(turn, agent_id, shadow):
    e = _event(turn, agent_id)
    e["state_context"]["shadow_state"] = shadow
    return e


def test_avg_exploration_density_single_run():
    # 16 cells observed out of 64 = 25%
    shadow = {f"cell_status_{i}_0": "empty" for i in range(16)}
    events = [_event_with_shadow(0, "agent_a", shadow)]
    result = compute_avg_exploration_density([events])
    assert result["avg_pct"] == pytest.approx(25.0)
    assert len(result["per_run"]) == 1


def test_avg_exploration_density_averages_across_runs():
    shadow_a = {f"cell_status_{i}_0": "empty" for i in range(16)}  # 25%
    shadow_b = {f"cell_status_{i}_1": "empty" for i in range(32)}  # 50%
    run_a = [_event_with_shadow(0, "agent_a", shadow_a)]
    run_b = [_event_with_shadow(0, "agent_a", shadow_b)]
    result = compute_avg_exploration_density([run_a, run_b])
    assert result["avg_pct"] == pytest.approx(37.5)
