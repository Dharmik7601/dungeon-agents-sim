"""Tests for the Streamlit dashboard — render_html_grid, list_log_files, and imports."""

import json
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Task 1 — dependency imports
# ---------------------------------------------------------------------------

def test_streamlit_importable():
    import streamlit  # noqa: F401


def test_pandas_importable():
    import pandas  # noqa: F401


def test_plotly_importable():
    import plotly  # noqa: F401


# ---------------------------------------------------------------------------
# Task 2 — render_html_grid
# ---------------------------------------------------------------------------

from src.cli.streamlit_app import render_html_grid  # noqa: E402


def _make_grid(cell_overrides=None):
    """Return a minimal 3x3 grid_data dict — all empty unless overridden."""
    data = {}
    if cell_overrides:
        data.update(cell_overrides)
    return data


def test_html_grid_empty_cell():
    """Empty cells render the '·' symbol."""
    html = render_html_grid({}, {}, width=2, height=2)
    assert "·" in html


def test_html_grid_wall_cell():
    html = render_html_grid({"cell_status_0_0": "wall"}, {}, width=2, height=2)
    assert "█" in html


def test_html_grid_key_cell():
    html = render_html_grid({"cell_status_1_0": "key"}, {}, width=2, height=2)
    assert "K" in html


def test_html_grid_locked_exit():
    html = render_html_grid({"cell_status_0_1": "exit_locked"}, {}, width=2, height=2)
    assert "X" in html


def test_html_grid_open_exit():
    html = render_html_grid({"cell_status_0_1": "exit_unlocked"}, {}, width=2, height=2)
    assert "O" in html


def test_html_grid_agent_a_overlay():
    """Agent A position renders 'A' regardless of underlying cell."""
    html = render_html_grid(
        {},
        {"agent_a": [0, 0]},
        width=2,
        height=2,
    )
    assert "A" in html


def test_html_grid_agent_b_overlay():
    html = render_html_grid(
        {},
        {"agent_b": [1, 1]},
        width=2,
        height=2,
    )
    assert "B" in html


def test_html_grid_both_agents_same_cell():
    """Both agents on same cell renders '✦'."""
    html = render_html_grid(
        {},
        {"agent_a": [0, 0], "agent_b": [0, 0]},
        width=2,
        height=2,
    )
    assert "✦" in html


def test_html_grid_fog_of_war_unseen_cell():
    """Cell absent from shadow_filter renders as '?' (fog of war)."""
    # shadow_filter is an empty set — no cells observed
    html = render_html_grid(
        {"cell_status_0_0": "wall"},
        {},
        width=2,
        height=2,
        shadow_filter=set(),
    )
    # Wall symbol should NOT appear; fog symbol should
    assert "█" not in html
    assert "?" in html


def test_html_grid_fog_of_war_seen_cell():
    """Cell present in shadow_filter renders normally despite fog mode."""
    html = render_html_grid(
        {"cell_status_0_0": "wall"},
        {},
        width=2,
        height=2,
        shadow_filter={"cell_status_0_0"},
    )
    assert "█" in html


def test_html_grid_no_shadow_filter_shows_all():
    """When shadow_filter is None (default), all cells render normally."""
    html = render_html_grid(
        {"cell_status_0_0": "wall"},
        {},
        width=2,
        height=2,
    )
    assert "█" in html
    assert "?" not in html


def test_html_grid_returns_html_table():
    """Output must be an HTML string containing a table tag."""
    html = render_html_grid({}, {}, width=2, height=2)
    assert "<table" in html
    assert "</table>" in html


# ---------------------------------------------------------------------------
# Task 3 — list_log_files
# ---------------------------------------------------------------------------

from src.cli.streamlit_app import list_log_files  # noqa: E402


def test_list_log_files_returns_sorted_paths(tmp_path):
    """Returns run_*.json files sorted by name, excluding WIP files."""
    (tmp_path / "run_abc.json").write_text("[]")
    (tmp_path / "run_def.json").write_text("[]")
    (tmp_path / "run_wip_xyz.json").write_text("[]")  # must be excluded

    result = list_log_files(tmp_path)

    names = [p.name for p in result]
    assert names == ["run_abc.json", "run_def.json"]


def test_list_log_files_excludes_wip_files(tmp_path):
    """WIP files are excluded even when they match run_*.json glob."""
    (tmp_path / "run_wip_001.json").write_text("[]")

    result = list_log_files(tmp_path)
    assert result == []


def test_list_log_files_empty_directory(tmp_path):
    """Returns empty list when no matching files exist."""
    result = list_log_files(tmp_path)
    assert result == []


def test_list_log_files_ignores_non_json(tmp_path):
    """Non-JSON files are not included."""
    (tmp_path / "run_abc.txt").write_text("data")
    (tmp_path / "run_abc.json").write_text("[]")

    result = list_log_files(tmp_path)
    assert len(result) == 1
    assert result[0].name == "run_abc.json"
