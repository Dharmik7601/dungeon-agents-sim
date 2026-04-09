"""Ground truth world state — the authoritative dungeon representation."""

from dataclasses import dataclass, field
from enum import Enum


class CellType(Enum):
    EMPTY = "empty"
    WALL = "wall"
    KEY = "key"
    EXIT_LOCKED = "exit_locked"
    EXIT_UNLOCKED = "exit_unlocked"


@dataclass
class WorldState:
    grid: list[list[CellType]]
    key_pos: tuple[int, int]
    exit_pos: tuple[int, int]
    agent_positions: dict[str, tuple[int, int]]
    exit_locked: bool = True
    turn_number: int = 0

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if (x, y) falls within the grid."""
        return 0 <= x < len(self.grid[0]) and 0 <= y < len(self.grid)
