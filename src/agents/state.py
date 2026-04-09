"""Per-agent mutable state and shared data types."""

from dataclasses import dataclass, field

from src.world.state import CellType


class ParseError(Exception):
    """Raised when the LLM returns a response that cannot be parsed as JSON."""


@dataclass
class ToolResult:
    status: str   # "success" | "failure"
    message: str
    data: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    reasoning: str
    expected_state: dict
    tool_name: str
    arguments: dict


@dataclass
class AgentState:
    agent_id: str
    position: tuple[int, int]
    inventory: list[str] = field(default_factory=list)
    shadow_map: dict[tuple[int, int], CellType] = field(default_factory=dict)
    message_inbox: list[str] = field(default_factory=list)
    message_outbox: list[str] = field(default_factory=list)
    consecutive_invalid_actions: int = 0
    consecutive_parse_failures: int = 0
    last_known_position: tuple[int, int] | None = None
    last_known_position_turn: int | None = None
