"""Tests for src/cli/diagnostic_viewer.py"""
import io
import json

import pytest
from rich.console import Console


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _success_event(agent_id="agent_a", turn=1):
    return {
        "event_id": "evt-001",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "turn_number": turn,
        "agent_id": agent_id,
        "action": {
            "tool_name": "move",
            "arguments": {"direction": "north"},
        },
        "state_context": {
            "agent_beliefs": {
                "reasoning": "Moving north to explore.",
                "expected_state": {},
            },
        },
        "execution_result": {
            "status": "success",
            "error_message": None,
            "deltas": [],
        },
    }


def _failure_event(agent_id="agent_a", turn=2):
    return {
        "event_id": "evt-002",
        "timestamp": "2024-01-01T00:00:01+00:00",
        "turn_number": turn,
        "agent_id": agent_id,
        "action": {
            "tool_name": "pick_up",
            "arguments": {"item": "key"},
        },
        "state_context": {
            "agent_beliefs": {
                "reasoning": "I believe the key is here.",
                "expected_state": {},
            },
        },
        "execution_result": {
            "status": "failure",
            "error_message": "No item here.",
            "deltas": [
                {
                    "property_key": "cell_contents_3_4",
                    "expected_value": ["key"],
                    "actual_value": [],
                    "discrepancy_source": "stale_shadow_state",
                }
            ],
        },
    }


def _make_console():
    buf = io.StringIO()
    return Console(file=buf, highlight=False, width=120), buf


# ---------------------------------------------------------------------------
# Unit: _fmt_diff
# ---------------------------------------------------------------------------

class TestFmtDiff:
    def test_formats_property_key(self):
        from src.cli.diagnostic_viewer import _fmt_diff
        deltas = [
            {
                "property_key": "cell_contents_3_4",
                "expected_value": ["key"],
                "actual_value": [],
                "discrepancy_source": "stale_shadow_state",
            }
        ]
        result = _fmt_diff(deltas)
        assert "cell_contents_3_4" in result

    def test_formats_discrepancy_source(self):
        from src.cli.diagnostic_viewer import _fmt_diff
        deltas = [
            {
                "property_key": "cell_status_1_2",
                "expected_value": "wall",
                "actual_value": "empty",
                "discrepancy_source": "fog_of_war",
            }
        ]
        result = _fmt_diff(deltas)
        assert "fog_of_war" in result

    def test_formats_expected_and_actual(self):
        from src.cli.diagnostic_viewer import _fmt_diff
        deltas = [
            {
                "property_key": "agent_inventory",
                "expected_value": ["key"],
                "actual_value": [],
                "discrepancy_source": "hallucination",
            }
        ]
        result = _fmt_diff(deltas)
        assert "EXPECTED" in result
        assert "ACTUAL" in result

    def test_formats_multiple_deltas(self):
        from src.cli.diagnostic_viewer import _fmt_diff
        deltas = [
            {
                "property_key": "cell_status_1_2",
                "expected_value": "wall",
                "actual_value": "empty",
                "discrepancy_source": "fog_of_war",
            },
            {
                "property_key": "agent_inventory",
                "expected_value": ["key"],
                "actual_value": [],
                "discrepancy_source": "hallucination",
            },
        ]
        result = _fmt_diff(deltas)
        assert "cell_status_1_2" in result
        assert "agent_inventory" in result

    def test_empty_deltas_returns_string(self):
        from src.cli.diagnostic_viewer import _fmt_diff
        result = _fmt_diff([])
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Unit: render_success
# ---------------------------------------------------------------------------

class TestRenderSuccess:
    def test_renders_turn_number(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(turn=7), console)
        assert "7" in buf.getvalue()

    def test_renders_agent_id(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(agent_id="agent_b"), console)
        assert "agent_b" in buf.getvalue()

    def test_renders_tool_name(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(), console)
        assert "move" in buf.getvalue()

    def test_renders_reasoning(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(), console)
        assert "Moving north to explore." in buf.getvalue()

    def test_does_not_print_panel(self):
        """Success renders as dim text + reasoning, not a Panel."""
        from src.cli.diagnostic_viewer import render_success
        from unittest.mock import MagicMock
        from rich.panel import Panel
        console = MagicMock()
        render_success(_success_event(), console)
        for call in console.print.call_args_list:
            args = call[0]
            if args:
                assert not isinstance(args[0], Panel), "Success must not render a Panel"


# ---------------------------------------------------------------------------
# Unit: render_incident
# ---------------------------------------------------------------------------

class TestRenderIncident:
    def test_prints_a_panel(self):
        from src.cli.diagnostic_viewer import render_incident
        from unittest.mock import MagicMock
        from rich.panel import Panel
        console = MagicMock()
        render_incident(_failure_event(), console)
        panel_calls = [
            c for c in console.print.call_args_list
            if c[0] and isinstance(c[0][0], Panel)
        ]
        assert len(panel_calls) >= 1, "render_incident must print a Panel"

    def test_panel_contains_tool_name(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)
        assert "pick_up" in buf.getvalue()

    def test_panel_contains_reasoning(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)
        assert "I believe the key is here." in buf.getvalue()

    def test_panel_contains_delta_property_key(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)
        assert "cell_contents_3_4" in buf.getvalue()

    def test_panel_contains_discrepancy_source(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)
        assert "stale_shadow_state" in buf.getvalue()


# ---------------------------------------------------------------------------
# Unit: render_log (filtering and agent scoping)
# ---------------------------------------------------------------------------

class TestRenderLog:
    def test_all_filter_renders_success_and_failure(self):
        from src.cli.diagnostic_viewer import render_log
        from unittest.mock import patch, call
        console, buf = _make_console()
        events = [_success_event(turn=1), _failure_event(turn=2)]
        with patch("src.cli.diagnostic_viewer.render_success") as mock_s, \
             patch("src.cli.diagnostic_viewer.render_incident") as mock_f:
            render_log(events, filter_mode="all", agent_filter=None, console=console)
            assert mock_s.call_count == 1
            assert mock_f.call_count == 1

    def test_failures_only_skips_success_events(self):
        from src.cli.diagnostic_viewer import render_log
        from unittest.mock import patch
        console, buf = _make_console()
        events = [_success_event(turn=1), _failure_event(turn=2)]
        with patch("src.cli.diagnostic_viewer.render_success") as mock_s, \
             patch("src.cli.diagnostic_viewer.render_incident") as mock_f:
            render_log(events, filter_mode="failures_only", agent_filter=None, console=console)
            assert mock_s.call_count == 0
            assert mock_f.call_count == 1

    def test_agent_filter_skips_other_agent(self):
        from src.cli.diagnostic_viewer import render_log
        from unittest.mock import patch
        events = [
            _success_event(agent_id="agent_a", turn=1),
            _success_event(agent_id="agent_b", turn=2),
        ]
        with patch("src.cli.diagnostic_viewer.render_success") as mock_s:
            console, _ = _make_console()
            render_log(events, filter_mode="all", agent_filter="agent_a", console=console)
            assert mock_s.call_count == 1
            rendered_event = mock_s.call_args[0][0]
            assert rendered_event["agent_id"] == "agent_a"

    def test_failures_only_on_all_successes_renders_nothing(self):
        from src.cli.diagnostic_viewer import render_log
        from unittest.mock import patch
        events = [_success_event(turn=1), _success_event(turn=2)]
        with patch("src.cli.diagnostic_viewer.render_success") as mock_s, \
             patch("src.cli.diagnostic_viewer.render_incident") as mock_f:
            console, _ = _make_console()
            render_log(events, filter_mode="failures_only", agent_filter=None, console=console)
            assert mock_s.call_count == 0
            assert mock_f.call_count == 0

    def test_empty_events_renders_nothing(self):
        from src.cli.diagnostic_viewer import render_log
        from unittest.mock import patch
        with patch("src.cli.diagnostic_viewer.render_success") as mock_s, \
             patch("src.cli.diagnostic_viewer.render_incident") as mock_f:
            console, _ = _make_console()
            render_log([], filter_mode="all", agent_filter=None, console=console)
            assert mock_s.call_count == 0
            assert mock_f.call_count == 0


# ---------------------------------------------------------------------------
# Unit: main — exit codes and argument parsing
# ---------------------------------------------------------------------------

class TestMainExitCodes:
    def test_nonexistent_log_file_exits_1(self):
        from src.cli.diagnostic_viewer import main
        with pytest.raises(SystemExit) as exc:
            main(["--log-file", "/nonexistent/path/run_fake.json"])
        assert exc.value.code == 1

    def test_invalid_json_exits_1(self, tmp_path):
        from src.cli.diagnostic_viewer import main
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            main(["--log-file", str(bad)])
        assert exc.value.code == 1

    def test_valid_file_does_not_exit_1(self, tmp_path):
        from src.cli.diagnostic_viewer import main
        log = tmp_path / "run.json"
        log.write_text(json.dumps([_success_event()]), encoding="utf-8")
        try:
            main(["--log-file", str(log)])
        except SystemExit as e:
            assert e.code == 0, f"Expected exit 0, got {e.code}"

    def test_empty_log_exits_cleanly(self, tmp_path):
        from src.cli.diagnostic_viewer import main
        log = tmp_path / "run_empty.json"
        log.write_text("[]", encoding="utf-8")
        try:
            main(["--log-file", str(log)])
        except SystemExit as e:
            assert e.code == 0, f"Expected exit 0, got {e.code}"

    def test_failures_only_no_failures_exits_cleanly(self, tmp_path):
        from src.cli.diagnostic_viewer import main
        log = tmp_path / "run_success_only.json"
        log.write_text(json.dumps([_success_event()]), encoding="utf-8")
        try:
            main(["--log-file", str(log), "--filter", "failures_only"])
        except SystemExit as e:
            assert e.code == 0, f"Expected exit 0, got {e.code}"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

def _event_with_agent_input(agent_id="agent_a", turn=3, status="success"):
    """Event fixture with full agent_input and shadow_state in state_context."""
    return {
        "event_id": "evt-003",
        "timestamp": "2024-01-01T00:00:02+00:00",
        "turn_number": turn,
        "agent_id": agent_id,
        "action": {
            "tool_name": "look",
            "arguments": {},
        },
        "state_context": {
            "agent_beliefs": {
                "reasoning": "Exploring the dungeon.",
                "expected_state": {},
            },
            "shadow_state": {
                "cell_status_0_0": "empty",
                "cell_status_1_0": "wall",
            },
            "agent_input": {
                "message_inbox": ["partner says: key is at (3,3)"],
                "last_mistake": {"tool_name": "move", "turn_number": 1, "reason": "wall"},
                "recent_calls": [
                    {"tool_name": "look", "arguments": {}, "turn_number": 0},
                    {"tool_name": "move", "arguments": {"direction": "east"}, "turn_number": 1},
                ],
                "last_known_location": {"position": [2, 4], "turn_number": 2},
            },
        },
        "execution_result": {
            "status": status,
            "error_message": None if status == "success" else "fail",
            "deltas": [],
        },
    }


class TestRenderSuccessAgentInput:
    def test_renders_message_inbox(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        assert "key is at (3,3)" in buf.getvalue()

    def test_renders_last_mistake(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        assert "move" in buf.getvalue()
        assert "wall" in buf.getvalue()

    def test_renders_recent_calls(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        out = buf.getvalue()
        assert "look" in out

    def test_renders_shadow_state_summary(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        out = buf.getvalue()
        # 2 cells in shadow_state
        assert "2" in out

    def test_no_crash_without_agent_input(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(), console)  # old event, no agent_input


class TestRenderIncidentAgentInput:
    def test_panel_contains_inbox(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "key is at (3,3)" in buf.getvalue()

    def test_panel_contains_last_mistake(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "wall" in buf.getvalue()

    def test_panel_contains_recent_calls(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "move" in buf.getvalue()

    def test_panel_contains_shadow_state(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        out = buf.getvalue()
        assert "wall" in out  # cell_status_1_0 is wall in shadow_state

    def test_no_crash_without_agent_input(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)  # old event, no agent_input


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_main_on_mixed_log_exits_0(self, tmp_path):
        """Running main on a valid mixed log (1 success + 1 failure) exits cleanly."""
        from src.cli.diagnostic_viewer import main
        events = [
            _success_event(agent_id="agent_a", turn=1),
            _failure_event(agent_id="agent_b", turn=2),
        ]
        log = tmp_path / "run_fixture.json"
        log.write_text(json.dumps(events), encoding="utf-8")
        try:
            main(["--log-file", str(log)])
        except SystemExit as e:
            assert e.code == 0, f"Expected exit 0, got {e.code}"

    def test_main_agent_filter_flag_accepted(self, tmp_path):
        """--agent flag is accepted and does not error."""
        from src.cli.diagnostic_viewer import main
        events = [_success_event(agent_id="agent_a", turn=1)]
        log = tmp_path / "run.json"
        log.write_text(json.dumps(events), encoding="utf-8")
        try:
            main(["--log-file", str(log), "--agent", "agent_a"])
        except SystemExit as e:
            assert e.code == 0

    def test_main_filter_agent_combination(self, tmp_path):
        """--filter failures_only and --agent agent_b together produce exit 0."""
        from src.cli.diagnostic_viewer import main
        events = [
            _success_event(agent_id="agent_a", turn=1),
            _failure_event(agent_id="agent_b", turn=2),
        ]
        log = tmp_path / "run.json"
        log.write_text(json.dumps(events), encoding="utf-8")
        try:
            main(["--log-file", str(log), "--filter", "failures_only", "--agent", "agent_b"])
        except SystemExit as e:
            assert e.code == 0


# ---------------------------------------------------------------------------
# Input / Output section labels and last_known_location and error_message
# ---------------------------------------------------------------------------

class TestRenderSuccessLabels:
    def test_shows_input_label(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        assert "Input" in buf.getvalue() or "INPUT" in buf.getvalue()

    def test_shows_output_label(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        assert "Output" in buf.getvalue() or "OUTPUT" in buf.getvalue()

    def test_shows_last_known_location(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_event_with_agent_input(), console)
        out = buf.getvalue()
        assert "2" in out and "4" in out  # position [2, 4]

    def test_no_crash_without_last_known_location(self):
        from src.cli.diagnostic_viewer import render_success
        console, buf = _make_console()
        render_success(_success_event(), console)  # old event, no agent_input


class TestRenderIncidentLabels:
    def test_panel_shows_input_label(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "Input" in buf.getvalue() or "INPUT" in buf.getvalue()

    def test_panel_shows_output_label(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "Output" in buf.getvalue() or "OUTPUT" in buf.getvalue()

    def test_panel_shows_result_label(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        assert "Result" in buf.getvalue() or "RESULT" in buf.getvalue()

    def test_panel_shows_error_message(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        event = _failure_event()  # has error_message "No item here."
        render_incident(event, console)
        assert "No item here." in buf.getvalue()

    def test_panel_shows_last_known_location(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_event_with_agent_input(status="failure"), console)
        out = buf.getvalue()
        assert "2" in out and "4" in out  # position [2, 4] from fixture

    def test_no_crash_without_last_known_location(self):
        from src.cli.diagnostic_viewer import render_incident
        console, buf = _make_console()
        render_incident(_failure_event(), console)
