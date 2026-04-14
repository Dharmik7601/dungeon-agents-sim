"""Semantic trace logger — records structured agent events with three-layer state diffs."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.agents.state import LLMResponse, ToolResult
from src.world.state import CellType, WorldState

_DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Keys produced for no-op tools (no deltas evaluated)
_NO_DELTA_TOOLS = {"look", "check_coordinates", "check_inventory", "send_message"}

# Map from CellType to its string key for ground-truth snapshots
_CELL_TYPE_NAMES: dict[CellType, str] = {ct: ct.value for ct in CellType}


# ---------------------------------------------------------------------------
# Ground truth serialisation
# ---------------------------------------------------------------------------

def _ground_truth_snapshot(world: WorldState) -> dict:
    """Flatten the WorldState into the standardised key format used by the schema.

    Empty cells are omitted to keep the snapshot sparse — the diagnostic viewer
    treats any missing cell_status key as "empty" by default.
    """
    snapshot: dict = {
        "grid_width": len(world.grid[0]) if world.grid else 0,
        "grid_height": len(world.grid),
    }
    for y, row in enumerate(world.grid):
        for x, cell in enumerate(row):
            if cell != CellType.EMPTY:
                snapshot[f"cell_status_{x}_{y}"] = cell.value
    for agent_id, pos in world.agent_positions.items():
        snapshot[f"{agent_id}_position"] = list(pos)
    return snapshot


# ---------------------------------------------------------------------------
# Delta computation — Scenario Mapping Matrix
# ---------------------------------------------------------------------------

def _compute_deltas(
    tool_name: str,
    expected_state: dict,
    shadow_state_before: dict[tuple, CellType],
    world: WorldState,
    agent_pos: tuple[int, int],
    agent_id: str = "",
) -> list[dict]:
    if tool_name in _NO_DELTA_TOOLS:
        return []

    ground_truth = _ground_truth_snapshot(world)
    deltas: list[dict] = []

    # Determine which expected_state keys to evaluate for this tool
    if tool_name == "move":
        keys_to_check = [k for k in expected_state if k.startswith("cell_status_")]

        # Check agent_position and partner_position explicitly — not part of keys_to_check
        # loop since they need direct position resolution rather than key lookup.
        if "agent_position" in expected_state:
            expected_pos = expected_state["agent_position"]
            actual_pos = list(agent_pos)
            if expected_pos != actual_pos:
                deltas.append({
                    "property_key": "agent_position",
                    "expected_value": expected_pos,
                    "actual_value": actual_pos,
                    "discrepancy_source": "stale_shadow_state",
                })

        if "partner_position" in expected_state:
            expected_pos = expected_state["partner_position"]
            # Find partner's actual position from ground_truth
            partner_actual = None
            for key, val in ground_truth.items():
                if key.endswith("_position") and key != f"{agent_id}_position":
                    partner_actual = val
                    break
            if partner_actual is not None and expected_pos != partner_actual:
                deltas.append({
                    "property_key": "partner_position",
                    "expected_value": expected_pos,
                    "actual_value": partner_actual,
                    "discrepancy_source": "stale_shadow_state",
                })
    elif tool_name == "pick_up":
        keys_to_check = [k for k in expected_state if k.startswith("cell_contents_")]
    elif tool_name == "use_item":
        keys_to_check = [k for k in expected_state
                         if k in ("agent_inventory",) or k.startswith("cell_status_")]
    else:
        keys_to_check = []

    for key in keys_to_check:
        expected_val = expected_state[key]
        actual_val = ground_truth.get(key)
        # Sparse snapshot omits empty cells; treat missing cell_status keys as "empty"
        # only when the coordinates are within the actual grid — OOB coordinates
        # have no ground truth at all and must remain None so the mismatch fires.
        if actual_val is None and key.startswith("cell_status_"):
            parts = key.replace("cell_status_", "").split("_")
            try:
                cx, cy = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                cx, cy = -1, -1
            grid_w = len(world.grid[0]) if world.grid else 0
            grid_h = len(world.grid)
            if 0 <= cx < grid_w and 0 <= cy < grid_h:
                actual_val = CellType.EMPTY.value

        # Normalise cell_contents keys: ground truth uses cell_status, not cell_contents
        # For pick_up we compare against whether the key item is still there
        if key.startswith("cell_contents_"):
            parts = key.split("_")   # cell_contents_X_Y
            x, y = int(parts[2]), int(parts[3])
            status_key = f"cell_status_{x}_{y}"
            actual_cell = world.grid[y][x]
            # Resolve what items are actually at this cell
            actual_contents = _cell_contents(actual_cell)
            actual_val = actual_contents
            if actual_val == expected_val:
                continue
        elif actual_val == expected_val:
            continue

        # Mismatch — classify discrepancy source
        if key.startswith("cell_status_") or key.startswith("cell_contents_"):
            parts = key.replace("cell_status_", "").replace("cell_contents_", "").split("_")
            try:
                cx, cy = int(parts[0]), int(parts[1])
                cell_key = (cx, cy)
            except (ValueError, IndexError):
                cell_key = None

            if cell_key and cell_key not in shadow_state_before:
                source = "fog_of_war"
            else:
                source = "stale_shadow_state"
        elif key == "agent_inventory":
            source = "stale_shadow_state"
        else:
            source = "hallucination"

        deltas.append({
            "property_key": key,
            "expected_value": expected_val,
            "actual_value": actual_val,
            "discrepancy_source": source,
        })

    return deltas


def _cell_contents(cell: CellType) -> list[str]:
    if cell == CellType.KEY:
        return ["key"]
    if cell in (CellType.EXIT_LOCKED, CellType.EXIT_UNLOCKED):
        return ["exit"]
    return []


# ---------------------------------------------------------------------------
# SemanticLogger
# ---------------------------------------------------------------------------

class SemanticLogger:
    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[dict] = []
        # WIP file written after every event so traces survive crashes.
        # Deleted by flush() once the final named file is written.
        self._wip_path: Path | None = None

    def _wip(self) -> Path:
        """Return (and lazily create) the crash-recovery WIP file path."""
        if self._wip_path is None:
            self._wip_path = self._data_dir / f"run_wip_{uuid.uuid4().hex[:8]}.json"
        return self._wip_path

    def log_event(
        self,
        *,
        turn_number: int,
        agent_id: str,
        llm_response: LLMResponse,
        shadow_state_before: dict,
        tool_result: ToolResult,
        world: WorldState,
        message_inbox: list | None = None,
        recent_calls_before: list | None = None,
        last_mistake_before: dict | None = None,
        last_known_location_before: dict | None = None,
    ) -> None:
        agent_pos = world.agent_positions.get(agent_id, (0, 0))
        ground_truth = _ground_truth_snapshot(world)
        shadow_serialised = {
            f"cell_status_{x}_{y}": ct.value
            for (x, y), ct in shadow_state_before.items()
        }
        deltas = _compute_deltas(
            llm_response.tool_name,
            llm_response.expected_state,
            shadow_state_before,
            world,
            agent_pos,
            agent_id,
        )

        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turn_number": turn_number,
            "agent_id": agent_id,
            "action": {
                "tool_name": llm_response.tool_name,
                "arguments": llm_response.arguments,
                "spatial_context": {
                    "agent_position": list(agent_pos),
                    "target_position": _resolve_target(
                        llm_response.tool_name, llm_response.arguments, agent_pos, world
                    ),
                },
            },
            "state_context": {
                "agent_beliefs": {
                    "reasoning": llm_response.reasoning,
                    "expected_state": llm_response.expected_state,
                },
                "shadow_state": shadow_serialised,
                "ground_truth": ground_truth,
                "agent_input": {
                    "message_inbox": list(message_inbox) if message_inbox else [],
                    "recent_calls": list(recent_calls_before) if recent_calls_before else [],
                    "last_mistake": dict(last_mistake_before) if last_mistake_before else None,
                    "last_known_location": dict(last_known_location_before) if last_known_location_before else None,
                },
            },
            "execution_result": {
                "status": tool_result.status,
                "error_message": tool_result.message if tool_result.status == "failure" else None,
                "deltas": deltas,
            },
        }
        self._events.append(event)
        # Write immediately so events survive a crash.
        self._wip().write_text(json.dumps(self._events, indent=2), encoding="utf-8")

    def flush(self, run_id: str = "") -> str:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        suffix = f"_{run_id}" if run_id else ""
        path = self._data_dir / f"run{suffix}_{ts}.json"
        path.write_text(json.dumps(self._events, indent=2), encoding="utf-8")
        # Remove the WIP file now that the final file exists.
        if self._wip_path and self._wip_path.exists():
            self._wip_path.unlink()
        return str(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIRECTION_OFFSETS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def _resolve_target(
    tool_name: str,
    arguments: dict,
    agent_pos: tuple[int, int],
    world: WorldState,
) -> list[int] | None:
    if tool_name == "move":
        direction = arguments.get("direction", "")
        offset = _DIRECTION_OFFSETS.get(direction)
        if offset:
            return [agent_pos[0] + offset[0], agent_pos[1] + offset[1]]
    elif tool_name in ("pick_up", "check_coordinates"):
        return list(agent_pos)
    elif tool_name == "use_item" and world.exit_pos:
        return list(world.exit_pos)
    return None
