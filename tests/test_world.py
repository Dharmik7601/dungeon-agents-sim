"""Tests for src/world/state.py and src/world/generator.py."""

from unittest.mock import patch

import pytest

from src.world.state import CellType, WorldState
from src.world.generator import bfs_path_exists, generate_map, generate_valid_world


# ---------------------------------------------------------------------------
# CellType
# ---------------------------------------------------------------------------

def test_celltype_has_all_members():
    members = {m.name for m in CellType}
    assert members == {"EMPTY", "WALL", "KEY", "EXIT_LOCKED", "EXIT_UNLOCKED"}


# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------

def test_worldstate_defaults():
    grid = [[CellType.EMPTY] * 8 for _ in range(8)]
    ws = WorldState(
        grid=grid,
        key_pos=(1, 1),
        exit_pos=(6, 6),
        agent_positions={"agent_a": (0, 0), "agent_b": (7, 7)},
    )
    assert ws.exit_locked is True
    assert ws.turn_number == 0


def test_worldstate_in_bounds():
    grid = [[CellType.EMPTY] * 8 for _ in range(8)]
    ws = WorldState(grid=grid, key_pos=(1, 1), exit_pos=(6, 6),
                    agent_positions={"agent_a": (0, 0), "agent_b": (7, 7)})
    assert ws.in_bounds(0, 0) is True
    assert ws.in_bounds(7, 7) is True
    assert ws.in_bounds(-1, 0) is False
    assert ws.in_bounds(0, 8) is False


# ---------------------------------------------------------------------------
# bfs_path_exists
# ---------------------------------------------------------------------------

def _open_grid(size=8):
    return [[CellType.EMPTY] * size for _ in range(size)]


def _walled_grid(size=8):
    grid = [[CellType.WALL] * size for _ in range(size)]
    grid[0][0] = CellType.EMPTY
    grid[7][7] = CellType.EMPTY
    return grid


def test_bfs_finds_path_on_open_grid():
    assert bfs_path_exists(_open_grid(), (0, 0), (7, 7)) is True


def test_bfs_returns_false_on_blocked_grid():
    assert bfs_path_exists(_walled_grid(), (0, 0), (7, 7)) is False


def test_bfs_start_equals_goal():
    assert bfs_path_exists(_open_grid(), (3, 3), (3, 3)) is True


def test_bfs_treats_exit_locked_as_passable():
    grid = _open_grid()
    grid[4][4] = CellType.EXIT_LOCKED
    assert bfs_path_exists(grid, (0, 0), (7, 7)) is True


# ---------------------------------------------------------------------------
# generate_map
# ---------------------------------------------------------------------------

def test_generate_map_returns_8x8_grid():
    ws = generate_map(8, 8, seed=42)
    assert len(ws.grid) == 8
    assert all(len(row) == 8 for row in ws.grid)


def test_generate_map_wall_density_cap():
    for seed in range(20):
        ws = generate_map(8, 8, seed=seed)
        total = 8 * 8
        walls = sum(cell == CellType.WALL for row in ws.grid for cell in row)
        assert walls / total <= 0.15, f"seed={seed}: wall density {walls/total:.2%} exceeds 15%"


def test_generate_map_entity_positions_on_non_wall_cells():
    for seed in range(20):
        ws = generate_map(8, 8, seed=seed)
        assert ws.grid[ws.key_pos[1]][ws.key_pos[0]] == CellType.KEY
        assert ws.grid[ws.exit_pos[1]][ws.exit_pos[0]] == CellType.EXIT_LOCKED
        for pos in ws.agent_positions.values():
            assert ws.grid[pos[1]][pos[0]] == CellType.EMPTY


def test_generate_map_no_two_entities_share_cell():
    for seed in range(20):
        ws = generate_map(8, 8, seed=seed)
        positions = [ws.key_pos, ws.exit_pos] + list(ws.agent_positions.values())
        assert len(positions) == len(set(positions)), f"seed={seed}: duplicate entity positions"


def test_generate_map_all_positions_in_bounds():
    ws = generate_map(8, 8, seed=0)
    for pos in [ws.key_pos, ws.exit_pos] + list(ws.agent_positions.values()):
        assert ws.in_bounds(*pos), f"Position {pos} out of bounds"


# ---------------------------------------------------------------------------
# generate_valid_world
# ---------------------------------------------------------------------------

def test_generate_valid_world_returns_solvable_map_across_seeds():
    for seed in range(50):
        ws = generate_valid_world(seed=seed)
        key = ws.key_pos
        exit_ = ws.exit_pos
        agent_a = ws.agent_positions["agent_a"]
        agent_b = ws.agent_positions["agent_b"]
        assert bfs_path_exists(ws.grid, agent_a, key), f"seed={seed}: agent_a cannot reach key"
        assert bfs_path_exists(ws.grid, agent_b, key), f"seed={seed}: agent_b cannot reach key"
        assert bfs_path_exists(ws.grid, key, exit_), f"seed={seed}: key cannot reach exit"


def test_generate_valid_world_grid_is_8x8():
    ws = generate_valid_world(seed=0)
    assert len(ws.grid) == 8
    assert all(len(row) == 8 for row in ws.grid)


def test_generate_valid_world_raises_after_max_retries():
    with patch("src.world.generator.generate_map") as mock_gen:
        # Return a map where no paths exist (all walls except corners)
        grid = [[CellType.WALL] * 8 for _ in range(8)]
        grid[0][0] = CellType.EMPTY
        grid[7][7] = CellType.EMPTY
        mock_gen.return_value = WorldState(
            grid=grid,
            key_pos=(7, 7),
            exit_pos=(0, 7),
            agent_positions={"agent_a": (0, 0), "agent_b": (1, 0)},
        )
        with pytest.raises(RuntimeError, match="Could not generate"):
            generate_valid_world()
