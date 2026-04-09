"""Entry point — generates a world, wires up agents and LLM clients, runs the simulation."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from types import SimpleNamespace

from rich.console import Console
from rich.rule import Rule

from src.agents.llm_client import LLMClient
from src.agents.state import AgentState
from src.cli.board_renderer import board_legend, render_board_live
from src.loop.game_loop import EndCondition, GameLoop
from src.tracing.langfuse_wrapper import flush_langfuse, wrap_with_langfuse
from src.tracing.semantic_logger import SemanticLogger
from src.world.generator import generate_valid_world
from src.world.state import WorldState

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "agent_system.md"
_MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemma-4-31b-it")
_MAX_TURN_LINES = 15  # status lines kept on screen


class _CompositeLogger:
    """Prints a refreshed board + status log AND delegates to SemanticLogger."""

    def __init__(self, run_id: str, semantic: SemanticLogger, console: Console) -> None:
        self._run_id = run_id
        self._semantic = semantic
        self._console = console
        self._turn_lines: list[str] = []

    def log_event(
        self,
        *,
        turn_number,
        agent_id,
        llm_response,
        tool_result,
        world: WorldState | None = None,
        **kwargs,
    ):
        status = "✓" if tool_result.status == "success" else "✗"
        line = (
            f"[Run {self._run_id}] Turn {turn_number:>2}: "
            f"{agent_id} {status} {llm_response.tool_name}({_fmt_args(llm_response.arguments)})"
            f"  → {tool_result.message}"
        )
        self._turn_lines.append(line)
        if world is not None:
            self._refresh(world)
        self._semantic.log_event(
            turn_number=turn_number,
            agent_id=agent_id,
            llm_response=llm_response,
            tool_result=tool_result,
            world=world,
            **kwargs,
        )

    def _refresh(self, world: WorldState) -> None:
        self._console.clear()
        self._console.print(render_board_live(world))
        self._console.print(board_legend())
        self._console.print(Rule(style="dim"))
        for line in self._turn_lines[-_MAX_TURN_LINES:]:
            self._console.print(line)

    def flush(self) -> str | None:
        return self._semantic.flush(run_id=self._run_id)


def _fmt_args(args: dict) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def run(run_id: str = "01") -> None:
    console = Console()

    console.print(f"[Run {run_id}] Generating dungeon world …")
    world = generate_valid_world()

    agent_a = AgentState(agent_id="agent_a", position=world.agent_positions["agent_a"])
    agent_b = AgentState(agent_id="agent_b", position=world.agent_positions["agent_b"])

    # Show initial board
    console.clear()
    console.print(render_board_live(world))
    console.print(board_legend())
    console.print(Rule(style="dim"))
    console.print(f"[Run {run_id}] Starting simulation (max 50 turns) …")

    llm_a_client = LLMClient(model_name=_MODEL_NAME, prompt_path=str(_PROMPT_PATH))
    llm_b_client = LLMClient(model_name=_MODEL_NAME, prompt_path=str(_PROMPT_PATH))

    semantic = SemanticLogger()
    logger = _CompositeLogger(run_id, semantic, console)

    # Wrap LLM clients with Langfuse tracing (no-op if env vars absent).
    # SimpleNamespace stores callables in instance __dict__, avoiding Python's
    # descriptor protocol that would otherwise bind the instance as a spurious
    # first argument when the function is accessed as an attribute.
    llm_a = SimpleNamespace(get_decision=wrap_with_langfuse(llm_a_client, run_id, 0, "agent_a"))
    llm_b = SimpleNamespace(get_decision=wrap_with_langfuse(llm_b_client, run_id, 0, "agent_b"))

    loop = GameLoop(world, agent_a, agent_b, llm_a, llm_b, logger)
    result = loop.run()

    # Flush Langfuse before exit so no traces are dropped.
    flush_langfuse()

    console.print(Rule(style="dim"))
    console.print(
        f"[Run {run_id}] Simulation ended — "
        f"[bold]{result.end_condition.value.upper()}[/bold] at turn {result.turn_number}"
    )
    if result.log_path:
        console.print(f"[Run {run_id}] Semantic log written to: {result.log_path}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else "01"
    run(run_id)
