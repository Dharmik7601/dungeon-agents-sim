"""Procedural dungeon generation with BFS solvability validation."""

import random
from collections import deque

from src.world.state import CellType, WorldState

_MAX_RETRIES = 100
_WALL_DENSITY = 0.15


def bfs_path_exists(
    grid: list[list[CellType]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> bool:
    """Return True if a traversable path exists from start to goal.

    WALL cells are impassable. All other cell types are treated as passable
    so that BFS can validate paths through keys and locked exits.
    """
    if start == goal:
        return True

    rows = len(grid)
    cols = len(grid[0])
    visited = {start}
    queue = deque([start])

    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in visited:
                if grid[ny][nx] != CellType.WALL:
                    if (nx, ny) == goal:
                        return True
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    return False


def generate_map(width: int, height: int, seed: int | None = None) -> WorldState:
    """Generate a raw (unvalidated) dungeon map."""
    rng = random.Random(seed)

    grid = [[CellType.EMPTY] * width for _ in range(height)]

    # Place walls up to the density cap
    max_walls = int(width * height * _WALL_DENSITY)
    all_cells = [(x, y) for y in range(height) for x in range(width)]
    wall_cells = rng.sample(all_cells, max_walls)
    for x, y in wall_cells:
        grid[y][x] = CellType.WALL

    # Pick non-wall cells for entities, ensuring no overlaps
    available = [c for c in all_cells if grid[c[1]][c[0]] == CellType.EMPTY]
    chosen = rng.sample(available, 4)  # key, exit, agent_a, agent_b

    key_pos = chosen[0]
    exit_pos = chosen[1]
    agent_a_pos = chosen[2]
    agent_b_pos = chosen[3]

    grid[key_pos[1]][key_pos[0]] = CellType.KEY
    grid[exit_pos[1]][exit_pos[0]] = CellType.EXIT_LOCKED

    return WorldState(
        grid=grid,
        key_pos=key_pos,
        exit_pos=exit_pos,
        agent_positions={"agent_a": agent_a_pos, "agent_b": agent_b_pos},
    )


def generate_valid_world(seed: int | None = None) -> WorldState:
    """Return a solvable dungeon world, regenerating until BFS passes.

    Validates three paths: agent_a→key, agent_b→key, key→exit.
    Raises RuntimeError after _MAX_RETRIES unsuccessful attempts.
    """
    rng = random.Random(seed)

    for _ in range(_MAX_RETRIES):
        attempt_seed = rng.randint(0, 10_000_000)
        ws = generate_map(8, 8, seed=attempt_seed)

        agent_a = ws.agent_positions["agent_a"]
        agent_b = ws.agent_positions["agent_b"]

        if (
            bfs_path_exists(ws.grid, agent_a, ws.key_pos)
            and bfs_path_exists(ws.grid, agent_b, ws.key_pos)
            and bfs_path_exists(ws.grid, ws.key_pos, ws.exit_pos)
        ):
            return ws

    raise RuntimeError(
        f"Could not generate a valid dungeon world after {_MAX_RETRIES} attempts."
    )
