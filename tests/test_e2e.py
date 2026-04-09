"""End-to-end smoke test: full simulation produces a valid run_*.json, CLI viewer exits cleanly."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.state import AgentState, LLMResponse
from src.loop.game_loop import GameLoop
from src.tracing.semantic_logger import SemanticLogger
from src.world.generator import generate_valid_world


def _mock_llm(tool_name="look", arguments=None):
    """Return a mock LLM that always returns the given tool decision."""
    llm = MagicMock()
    llm.get_decision.return_value = LLMResponse(
        reasoning="Smoke test decision.",
        expected_state={},
        tool_name=tool_name,
        arguments=arguments or {},
    )
    return llm


def _build_loop(tmp_path, run_id="e2e", max_turns=3):
    """Build a GameLoop wired to a SemanticLogger writing to tmp_path."""
    world = generate_valid_world()
    agent_a = AgentState(agent_id="agent_a", position=world.agent_positions["agent_a"])
    agent_b = AgentState(agent_id="agent_b", position=world.agent_positions["agent_b"])
    semantic = SemanticLogger(data_dir=str(tmp_path))

    # SemanticLogger.flush(run_id="") accepts no args — wrapping so flush() passes run_id
    class _BoundLogger:
        def log_event(self, **kwargs):
            semantic.log_event(**kwargs)

        def flush(self):
            return semantic.flush(run_id=run_id)

    loop = GameLoop(
        world, agent_a, agent_b,
        _mock_llm("look"), _mock_llm("look"),
        _BoundLogger(), max_turns=max_turns,
    )
    return loop


class TestEndToEnd:
    def test_simulation_writes_json_log(self, tmp_path):
        """A completed simulation writes a run_*.json file to the data directory."""
        result = _build_loop(tmp_path).run()
        assert result.log_path is not None
        assert Path(result.log_path).exists(), f"Log file not found: {result.log_path}"

    def test_log_contains_events(self, tmp_path):
        """The log file contains at least one event (one per agent turn)."""
        result = _build_loop(tmp_path).run()
        events = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
        assert isinstance(events, list)
        assert len(events) > 0

    def test_event_schema_has_required_top_level_keys(self, tmp_path):
        """Every event in the log has the required top-level schema keys."""
        result = _build_loop(tmp_path).run()
        events = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
        required_keys = {"event_id", "timestamp", "turn_number", "agent_id",
                         "action", "state_context", "execution_result"}
        for event in events:
            missing = required_keys - set(event.keys())
            assert not missing, f"Event missing keys: {missing}"

    def test_event_schema_has_three_layer_state_context(self, tmp_path):
        """state_context in each event has all three state layers."""
        result = _build_loop(tmp_path).run()
        events = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
        for event in events:
            sc = event["state_context"]
            assert "agent_beliefs" in sc
            assert "shadow_state" in sc
            assert "ground_truth" in sc

    def test_event_schema_has_execution_result_fields(self, tmp_path):
        """execution_result in each event has status and deltas fields."""
        result = _build_loop(tmp_path).run()
        events = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
        for event in events:
            er = event["execution_result"]
            assert "status" in er
            assert "deltas" in er

    def test_event_agent_ids_are_valid(self, tmp_path):
        """All events have a recognized agent_id."""
        result = _build_loop(tmp_path).run()
        events = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
        for event in events:
            assert event["agent_id"] in ("agent_a", "agent_b")

    def test_cli_viewer_exits_0_on_simulation_log(self, tmp_path):
        """CLI viewer accepts simulation output and exits cleanly (code 0)."""
        from src.cli.diagnostic_viewer import main
        result = _build_loop(tmp_path).run()
        try:
            main(["--log-file", result.log_path])
        except SystemExit as exc:
            assert exc.code == 0, f"CLI viewer exited with code {exc.code}"

    def test_cli_viewer_failures_only_on_simulation_log(self, tmp_path):
        """CLI viewer --filter failures_only on an all-success log exits cleanly."""
        from src.cli.diagnostic_viewer import main
        result = _build_loop(tmp_path).run()
        try:
            main(["--log-file", result.log_path, "--filter", "failures_only"])
        except SystemExit as exc:
            assert exc.code == 0, f"CLI viewer exited with code {exc.code}"

    def test_cli_viewer_agent_filter_on_simulation_log(self, tmp_path):
        """CLI viewer --agent agent_a on simulation output exits cleanly."""
        from src.cli.diagnostic_viewer import main
        result = _build_loop(tmp_path).run()
        try:
            main(["--log-file", result.log_path, "--agent", "agent_a"])
        except SystemExit as exc:
            assert exc.code == 0, f"CLI viewer exited with code {exc.code}"
