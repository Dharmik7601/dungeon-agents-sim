"""Board rendering — shared by the live simulation display and the diagnostic viewer."""

from rich import box
from rich.columns import Columns
from rich.table import Table
from rich.text import Text

from src.world.state import CellType, WorldState

# Cell display: (symbol, style)
_CELL_DISPLAY: dict[CellType, tuple[str, str]] = {
    CellType.EMPTY:         ("·", "dim"),
    CellType.WALL:          ("█", "white"),
    CellType.KEY:           ("K", "yellow bold"),
    CellType.EXIT_LOCKED:   ("X", "red bold"),
    CellType.EXIT_UNLOCKED: ("O", "green bold"),
}

_VALUE_TO_CELL: dict[str, CellType] = {ct.value: ct for ct in CellType}

_LEGEND = (
    "[cyan bold]A[/cyan bold] agent_a  "
    "[blue bold]B[/blue bold] agent_b  "
    "[magenta bold]✦[/magenta bold] both  "
    "[yellow bold]K[/yellow bold] key  "
    "[red bold]X[/red bold] exit(locked)  "
    "[green bold]O[/green bold] exit(open)  "
    "[white]█[/white] wall"
)


def _build_grid_table(
    width: int,
    height: int,
    cell_fn,  # callable(x, y) -> Text
) -> Table:
    table = Table(
        box=box.SQUARE,
        show_header=False,
        padding=(0, 1),
        border_style="dim",
    )
    for _ in range(width):
        table.add_column(justify="center", width=2, no_wrap=True)
    for y in range(height):
        table.add_row(*[cell_fn(x, y) for x in range(width)])
    return table


def render_board_live(world: WorldState) -> Table:
    """Render the live game board from a WorldState object."""
    height = len(world.grid)
    width = len(world.grid[0]) if height else 0
    pos_a = world.agent_positions.get("agent_a", (-1, -1))
    pos_b = world.agent_positions.get("agent_b", (-1, -1))

    def cell_fn(x, y):
        if (x, y) == pos_a and (x, y) == pos_b:
            return Text("✦", style="magenta bold")
        if (x, y) == pos_a:
            return Text("A", style="cyan bold")
        if (x, y) == pos_b:
            return Text("B", style="blue bold")
        cell = world.grid[y][x]
        symbol, style = _CELL_DISPLAY.get(cell, ("?", ""))
        return Text(symbol, style=style)

    return _build_grid_table(width, height, cell_fn)


def render_board_from_snapshot(ground_truth: dict) -> Table:
    """Render the board from a ground_truth snapshot dict (from a semantic log event)."""
    if "grid_width" in ground_truth and "grid_height" in ground_truth:
        width = ground_truth["grid_width"]
        height = ground_truth["grid_height"]
    else:
        # Legacy fallback: infer from cell keys and agent positions
        max_x = max_y = 0
        for key in ground_truth:
            if key.startswith("cell_status_"):
                parts = key.split("_")
                max_x = max(max_x, int(parts[2]))
                max_y = max(max_y, int(parts[3]))
        for pos_key in ("agent_a_position", "agent_b_position"):
            pos = ground_truth.get(pos_key)
            if pos and pos[0] >= 0:
                max_x = max(max_x, pos[0])
                max_y = max(max_y, pos[1])
        width, height = max_x + 1, max_y + 1
    raw_a = ground_truth.get("agent_a_position", [-1, -1])
    raw_b = ground_truth.get("agent_b_position", [-1, -1])
    pos_a = (raw_a[0], raw_a[1])
    pos_b = (raw_b[0], raw_b[1])

    def cell_fn(x, y):
        if (x, y) == pos_a and (x, y) == pos_b:
            return Text("✦", style="magenta bold")
        if (x, y) == pos_a:
            return Text("A", style="cyan bold")
        if (x, y) == pos_b:
            return Text("B", style="blue bold")
        cell_value = ground_truth.get(f"cell_status_{x}_{y}", "empty")
        cell = _VALUE_TO_CELL.get(cell_value, CellType.EMPTY)
        symbol, style = _CELL_DISPLAY.get(cell, ("?", ""))
        return Text(symbol, style=style)

    return _build_grid_table(width, height, cell_fn)


def board_legend() -> str:
    return _LEGEND
