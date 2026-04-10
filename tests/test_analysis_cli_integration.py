"""Integration tests for single_run_analysis and cross_run_analysis CLI entry points."""

import pytest
from pathlib import Path

from src.cli.single_run_analysis import main as single_main
from src.cli.cross_run_analysis import main as cross_main

SAVED_LOGS = Path(__file__).parent.parent / "saved_logs"
FIRST_LOG = sorted(SAVED_LOGS.glob("run_*.json"))[0]


# ---------------------------------------------------------------------------
# single_run_analysis integration
# ---------------------------------------------------------------------------


def test_single_run_main_exits_cleanly_and_renders_all_sections(capsys):
    single_main(["--log-file", str(FIRST_LOG)])
    out = capsys.readouterr().out
    assert "A." in out
    assert "B." in out
    assert "C." in out
    assert "D." in out


def test_single_run_main_exits_nonzero_on_missing_file():
    with pytest.raises(SystemExit):
        single_main(["--log-file", "nonexistent_run.json"])


# ---------------------------------------------------------------------------
# cross_run_analysis integration
# ---------------------------------------------------------------------------


def test_cross_run_main_exits_cleanly_and_renders_all_sections(capsys):
    cross_main(["--dir", str(SAVED_LOGS)])
    out = capsys.readouterr().out
    assert "A." in out
    assert "B." in out
    assert "C." in out
    assert "D." in out
    assert "E." in out


def test_cross_run_main_exits_nonzero_on_empty_directory(tmp_path):
    with pytest.raises(SystemExit):
        cross_main(["--dir", str(tmp_path)])
