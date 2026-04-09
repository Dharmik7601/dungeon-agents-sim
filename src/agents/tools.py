"""Tool dispatcher — validates and executes agent tool calls against ground truth."""

from src.agents.state import AgentState, ToolResult
from src.world.state import CellType, WorldState

_DIRECTIONS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}


def _adjacent_positions(x: int, y: int, world: WorldState) -> list[tuple[int, int]]:
    return [
        (x + dx, y + dy)
        for dx, dy in _DIRECTIONS.values()
        if world.in_bounds(x + dx, y + dy)
    ]


def _fail(agent: AgentState, message: str) -> ToolResult:
    agent.consecutive_invalid_actions += 1
    return ToolResult(status="failure", message=message)


def _succeed(agent: AgentState, message: str, data: dict | None = None) -> ToolResult:
    agent.consecutive_invalid_actions = 0
    return ToolResult(status="success", message=message, data=data or {})


class ToolDispatcher:

    @staticmethod
    def dispatch(
        tool_name: str,
        arguments: dict,
        agent: AgentState,
        world: WorldState,
    ) -> ToolResult:
        handler = _HANDLERS.get(tool_name)
        if handler is None:
            return _fail(agent, f"Unknown tool: '{tool_name}'")
        return handler(arguments, agent, world)


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------

def _move(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    direction = args.get("direction", "").lower()
    if direction not in _DIRECTIONS:
        return _fail(agent, f"Invalid direction: '{direction}'")

    dx, dy = _DIRECTIONS[direction]
    nx, ny = agent.position[0] + dx, agent.position[1] + dy

    if not world.in_bounds(nx, ny):
        return _fail(agent, f"Cannot move {direction}: out of bounds")

    if world.grid[ny][nx] == CellType.WALL:
        return _fail(agent, f"Cannot move {direction}: wall")

    agent.position = (nx, ny)
    world.agent_positions[agent.agent_id] = (nx, ny)
    agent.shadow_map[(nx, ny)] = world.grid[ny][nx]
    return _succeed(agent, f"Moved {direction} to ({nx}, {ny})", {"position": (nx, ny)})


def _look(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    x, y = agent.position
    cells_to_reveal = [(x, y)] + _adjacent_positions(x, y, world)
    for cx, cy in cells_to_reveal:
        agent.shadow_map[(cx, cy)] = world.grid[cy][cx]
    return _succeed(agent, f"Looked around ({x}, {y})", {"revealed": cells_to_reveal})


def _pick_up(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    item = args.get("item", "")
    x, y = agent.position
    cell = world.grid[y][x]

    item_cell_map = {"key": CellType.KEY}
    expected_cell = item_cell_map.get(item)

    if expected_cell is None or cell != expected_cell:
        return _fail(agent, f"No '{item}' at ({x}, {y})")

    agent.inventory.append(item)
    world.grid[y][x] = CellType.EMPTY
    if item == "key":
        world.key_pos = None
    agent.shadow_map[(x, y)] = CellType.EMPTY
    return _succeed(agent, f"Picked up '{item}'", {"item": item})


def _check_coordinates(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    agent.shadow_map[agent.position] = world.grid[agent.position[1]][agent.position[0]]
    agent.last_known_position = agent.position
    agent.last_known_position_turn = world.turn_number
    return _succeed(agent, f"Position is {agent.position}", {"position": agent.position})


def _check_inventory(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    return _succeed(agent, f"Inventory: {agent.inventory}", {"inventory": list(agent.inventory)})


def _use_item(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    item = args.get("item", "")
    target = args.get("target", "")

    if item not in agent.inventory:
        return _fail(agent, f"'{item}' not in inventory")

    if item == "key" and target == "exit":
        x, y = agent.position
        ex, ey = world.exit_pos
        adjacent_and_self = [(x, y)] + _adjacent_positions(x, y, world)
        if (ex, ey) not in adjacent_and_self:
            return _fail(agent, f"Exit at ({ex}, {ey}) is not adjacent to agent")
        if not world.exit_locked:
            return _fail(agent, "Exit is already unlocked")

        world.exit_locked = False
        world.grid[ey][ex] = CellType.EXIT_UNLOCKED
        agent.shadow_map[(ex, ey)] = CellType.EXIT_UNLOCKED
        return _succeed(agent, "Used key to unlock exit", {"exit_pos": (ex, ey)})

    return _fail(agent, f"Cannot use '{item}' on '{target}'")


def _send_message(args: dict, agent: AgentState, world: WorldState) -> ToolResult:
    message = args.get("message", "")
    recipient = args.get("agent", "")
    agent.message_outbox.append(message)
    return _succeed(agent, f"Message queued for {recipient}", {"message": message})


_HANDLERS = {
    "move": _move,
    "look": _look,
    "pick_up": _pick_up,
    "check_coordinates": _check_coordinates,
    "check_inventory": _check_inventory,
    "use_item": _use_item,
    "send_message": _send_message,
}
