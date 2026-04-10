"""Tests for src/cli/single_run_analysis.py — scaffold and Metric A."""

import json
import sys
from pathlib import Path

import pytest

from src.cli.single_run_analysis import (
    compute_agent_efficiency,
    compute_delusion_timeline,
    compute_map_coverage,
    compute_run_summary,
    derive_end_condition,
    load_events,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_EVENTS = [
    {
        "event_id": "abc",
        "turn_number": 0,
        "agent_id": "agent_a",
        "action": {"tool_name": "look", "arguments": {}},
        "state_context": {},
        "execution_result": {"status": "success", "error_message": None, "deltas": []},
    }
]


# ---------------------------------------------------------------------------
# load_events
# ---------------------------------------------------------------------------


def test_load_events_returns_list_from_valid_file(tmp_path):
    log = tmp_path / "run_test.json"
    log.write_text(json.dumps(MINIMAL_EVENTS), encoding="utf-8")
    result = load_events(log)
    assert result == MINIMAL_EVENTS


def test_load_events_exits_on_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(SystemExit):
        load_events(missing)


def test_load_events_exits_on_invalid_json(tmp_path):
    bad = tmp_path / "run_bad.json"
    bad.write_text("not valid json {{{", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_events(bad)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers to build minimal events
# ---------------------------------------------------------------------------


def _make_event(turn, agent_id, tool="look", status="success", gt=None, shadow=None):
    return {
        "event_id": f"e{turn}",
        "turn_number": turn,
        "agent_id": agent_id,
        "action": {"tool_name": tool, "arguments": {}},
        "state_context": {
            "ground_truth": gt or {"grid_width": 8, "grid_height": 8},
            "agent_input": {},
            "shadow_state": shadow if shadow is not None else {},
            "agent_beliefs": {"reasoning": "", "expected_state": {}},
        },
        "execution_result": {"status": status, "error_message": None, "deltas": []},
    }


def _success_gt(ax, ay, bx, by):
    """Ground truth where both agents are on the unlocked exit."""
    return {
        "grid_width": 8,
        "grid_height": 8,
        f"cell_status_{ax}_{ay}": "exit_unlocked",
        "agent_a_position": [ax, ay],
        "agent_b_position": [bx, by],
    }


def _running_gt(ax, ay, bx, by, ex, ey, kx=None, ky=None):
    """Ground truth for an in-progress or failed run."""
    gt = {
        "grid_width": 8,
        "grid_height": 8,
        f"cell_status_{ex}_{ey}": "exit_locked",
        "agent_a_position": [ax, ay],
        "agent_b_position": [bx, by],
    }
    if kx is not None:
        gt[f"cell_status_{kx}_{ky}"] = "key"
    return gt


# ---------------------------------------------------------------------------
# derive_end_condition
# ---------------------------------------------------------------------------


def test_derive_end_condition_success():
    gt = _success_gt(3, 3, 3, 3)
    events = [_make_event(5, "agent_a", gt=gt)]
    assert derive_end_condition(events) == "SUCCESS"


def test_derive_end_condition_turn_limit():
    gt = _running_gt(0, 0, 1, 1, 7, 7)
    events = [_make_event(50, "agent_b", gt=gt)]
    assert derive_end_condition(events) == "TURN_LIMIT"


def test_derive_end_condition_other_early_stop():
    gt = _running_gt(0, 0, 1, 1, 7, 7)
    events = [_make_event(13, "agent_a", gt=gt)]
    assert derive_end_condition(events) == "OTHER"


def test_derive_end_condition_unlocked_but_agents_not_both_there():
    # Door unlocked but agents are not both on it — not yet SUCCESS
    gt = {
        "grid_width": 8,
        "grid_height": 8,
        "cell_status_3_3": "exit_unlocked",
        "agent_a_position": [3, 3],
        "agent_b_position": [1, 1],  # B not at exit
    }
    events = [_make_event(20, "agent_b", gt=gt)]
    assert derive_end_condition(events) == "OTHER"


# ---------------------------------------------------------------------------
# compute_run_summary
# ---------------------------------------------------------------------------


def test_compute_run_summary_total_turns():
    gt = _running_gt(0, 0, 1, 1, 7, 7)
    events = [_make_event(0, "agent_a", gt={"grid_width": 8, "grid_height": 8}),
              _make_event(13, "agent_b", gt=gt)]
    summary = compute_run_summary(events)
    assert summary["total_turns"] == 13


def test_compute_run_summary_manhattan_distance_to_exit():
    # Agent A at (0,0), Agent B at (1,1), exit at (7,7)
    gt = _running_gt(0, 0, 1, 1, 7, 7)
    events = [_make_event(10, "agent_b", gt=gt)]
    summary = compute_run_summary(events)
    assert summary["dist_a_to_exit"] == 14  # |7-0| + |7-0|
    assert summary["dist_b_to_exit"] == 12  # |7-1| + |7-1|


def test_compute_run_summary_includes_key_distance_when_key_on_ground():
    # Key still at (5,5)
    gt = _running_gt(0, 0, 1, 1, 7, 7, kx=5, ky=5)
    events = [_make_event(10, "agent_b", gt=gt)]
    summary = compute_run_summary(events)
    assert summary["key_pos"] == [5, 5]
    assert summary["dist_a_to_key"] == 10  # |5-0| + |5-0|
    assert summary["dist_b_to_key"] == 8   # |5-1| + |5-1|


def test_compute_run_summary_omits_key_distance_when_key_picked_up():
    # No key cell in ground truth — it was picked up
    gt = _running_gt(0, 0, 1, 1, 7, 7)
    events = [_make_event(10, "agent_b", gt=gt)]
    summary = compute_run_summary(events)
    assert summary["key_pos"] is None
    assert summary["dist_a_to_key"] is None
    assert summary["dist_b_to_key"] is None


# ---------------------------------------------------------------------------
# compute_agent_efficiency
# ---------------------------------------------------------------------------


def _make_eff_event(turn, agent_id, tool, status="success"):
    return _make_event(turn, agent_id, tool=tool, status=status)


def test_agent_efficiency_tool_counts():
    events = [
        _make_eff_event(0, "agent_a", "look"),
        _make_eff_event(1, "agent_b", "move"),
        _make_eff_event(2, "agent_a", "move"),
        _make_eff_event(3, "agent_b", "move"),
        _make_eff_event(4, "agent_a", "look"),
    ]
    result = compute_agent_efficiency(events)
    assert result["agent_a"]["tool_counts"]["look"] == 2
    assert result["agent_a"]["tool_counts"]["move"] == 1
    assert result["agent_b"]["tool_counts"]["move"] == 2
    assert result["agent_a"]["total_actions"] == 3
    assert result["agent_b"]["total_actions"] == 2


def test_agent_efficiency_failure_count_and_error_rate():
    events = [
        _make_eff_event(0, "agent_a", "move", status="success"),
        _make_eff_event(1, "agent_a", "move", status="failure"),
        _make_eff_event(2, "agent_a", "move", status="failure"),
    ]
    result = compute_agent_efficiency(events)
    assert result["agent_a"]["failure_count"] == 2
    assert result["agent_a"]["error_rate"] == pytest.approx(200 / 3)


def test_agent_efficiency_zero_error_rate_when_no_failures():
    events = [
        _make_eff_event(0, "agent_a", "look"),
        _make_eff_event(1, "agent_a", "move"),
    ]
    result = compute_agent_efficiency(events)
    assert result["agent_a"]["error_rate"] == 0.0
    assert result["agent_a"]["failure_count"] == 0


def test_agent_efficiency_chatter_counts_only_send_message():
    events = [
        _make_eff_event(0, "agent_a", "send_message"),
        _make_eff_event(1, "agent_a", "move"),
        _make_eff_event(2, "agent_a", "send_message"),
        _make_eff_event(3, "agent_b", "look"),
    ]
    result = compute_agent_efficiency(events)
    assert result["agent_a"]["chatter"] == 2
    assert result["agent_b"]["chatter"] == 0


def test_agent_efficiency_single_action_agent():
    events = [_make_eff_event(0, "agent_a", "check_coordinates")]
    result = compute_agent_efficiency(events)
    assert result["agent_a"]["total_actions"] == 1
    assert result["agent_a"]["error_rate"] == 0.0


# ---------------------------------------------------------------------------
# compute_delusion_timeline
# ---------------------------------------------------------------------------


def _make_delta(prop, expected, actual, source="hallucination"):
    return {
        "property_key": prop,
        "expected_value": expected,
        "actual_value": actual,
        "discrepancy_source": source,
    }


def _make_event_with_deltas(turn, agent_id, deltas, shadow=None):
    e = _make_event(turn, agent_id, status="failure")
    e["execution_result"]["deltas"] = deltas
    if shadow is not None:
        e["state_context"]["shadow_state"] = shadow
    return e


def test_delusion_timeline_single_delta_produces_one_record():
    delta = _make_delta("cell_status_3_3", "empty", "wall")
    events = [_make_event_with_deltas(5, "agent_a", [delta])]
    timeline = compute_delusion_timeline(events)
    assert len(timeline) == 1
    rec = timeline[0]
    assert rec["turn"] == 5
    assert rec["agent_id"] == "agent_a"
    assert rec["property_key"] == "cell_status_3_3"
    assert rec["expected_value"] == "empty"
    assert rec["actual_value"] == "wall"
    assert rec["discrepancy_source"] == "hallucination"


def test_delusion_timeline_empty_deltas_produces_no_records():
    events = [_make_event_with_deltas(3, "agent_a", [])]
    assert compute_delusion_timeline(events) == []


def test_delusion_timeline_multiple_deltas_in_one_event():
    deltas = [
        _make_delta("cell_status_1_1", "empty", "wall"),
        _make_delta("cell_status_2_2", "key", "empty"),
    ]
    events = [_make_event_with_deltas(4, "agent_b", deltas)]
    timeline = compute_delusion_timeline(events)
    assert len(timeline) == 2
    assert timeline[0]["property_key"] == "cell_status_1_1"
    assert timeline[1]["property_key"] == "cell_status_2_2"


def test_delusion_timeline_time_to_correction_found():
    # Delta on turn 2; agent_a's shadow_state reflects actual_value on turn 6
    delta = _make_delta("cell_status_3_3", "empty", "wall")
    event_delta = _make_event_with_deltas(2, "agent_a", [delta], shadow={})
    event_no_fix = _make_event(4, "agent_a")
    event_no_fix["state_context"]["shadow_state"] = {}
    event_fixed = _make_event(6, "agent_a")
    event_fixed["state_context"]["shadow_state"] = {"cell_status_3_3": "wall"}
    events = [event_delta, event_no_fix, event_fixed]
    timeline = compute_delusion_timeline(events)
    assert timeline[0]["corrected_in"] == 4  # turn 6 - turn 2


def test_delusion_timeline_time_to_correction_never():
    # Shadow updated but still wrong value
    delta = _make_delta("cell_status_3_3", "empty", "wall")
    event_delta = _make_event_with_deltas(2, "agent_a", [delta], shadow={})
    event_later = _make_event(4, "agent_a")
    event_later["state_context"]["shadow_state"] = {"cell_status_3_3": "empty"}
    events = [event_delta, event_later]
    timeline = compute_delusion_timeline(events)
    assert timeline[0]["corrected_in"] == "never"


def test_delusion_timeline_non_cell_key_has_no_correction():
    delta = _make_delta("partner_position", [0, 0], [3, 3])
    events = [_make_event_with_deltas(2, "agent_a", [delta])]
    timeline = compute_delusion_timeline(events)
    assert timeline[0]["corrected_in"] is None


# ---------------------------------------------------------------------------
# compute_map_coverage
# ---------------------------------------------------------------------------


def _make_event_with_shadow(turn, agent_id, shadow):
    e = _make_event(turn, agent_id)
    e["state_context"]["shadow_state"] = shadow
    return e


def test_map_coverage_union_of_both_agents():
    events = [
        _make_event_with_shadow(0, "agent_a", {"cell_status_0_0": "empty", "cell_status_1_0": "wall"}),
        _make_event_with_shadow(1, "agent_b", {"cell_status_2_0": "empty"}),
    ]
    cov = compute_map_coverage(events)
    assert cov["observed"] == 3
    assert cov["total"] == 64
    assert cov["pct"] == pytest.approx(3 / 64 * 100)


def test_map_coverage_uses_last_shadow_per_agent():
    events = [
        _make_event_with_shadow(0, "agent_a", {"cell_status_0_0": "empty"}),
        _make_event_with_shadow(2, "agent_a", {"cell_status_0_0": "empty", "cell_status_1_0": "wall"}),
    ]
    cov = compute_map_coverage(events)
    assert cov["observed"] == 2


def test_map_coverage_ignores_non_cell_status_keys():
    events = [
        _make_event_with_shadow(0, "agent_a", {
            "cell_status_0_0": "empty",
            "agent_a_position": [0, 0],
        }),
    ]
    cov = compute_map_coverage(events)
    assert cov["observed"] == 1


def test_map_coverage_agent_with_empty_shadow_contributes_zero():
    events = [
        _make_event_with_shadow(0, "agent_a", {}),
        _make_event_with_shadow(1, "agent_b", {"cell_status_5_5": "empty"}),
    ]
    cov = compute_map_coverage(events)
    assert cov["observed"] == 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_header_with_event_count(tmp_path, capsys):
    log = tmp_path / "run_test.json"
    log.write_text(json.dumps(MINIMAL_EVENTS), encoding="utf-8")
    main(["--log-file", str(log)])
    out = capsys.readouterr().out
    assert "1" in out  # event count
    assert "run_test.json" in out  # filename
