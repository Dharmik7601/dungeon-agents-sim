"""Entry point — generates a world, wires up agents and LLM clients, runs the simulation."""

import os
import sys
from pathlib import Path

from src.agents.llm_client import LLMClient
from src.agents.state import AgentState
from src.loop.game_loop import EndCondition, GameLoop
from src.tracing.langfuse_wrapper import wrap_with_langfuse
from src.tracing.semantic_logger import SemanticLogger
from src.world.generator import generate_valid_world

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "agent_system.md"
_MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemma-3-27b-it")


class _CompositeLogger:
    """Prints status lines to stdout AND delegates to SemanticLogger for JSON output."""

    def __init__(self, run_id: str, semantic: SemanticLogger) -> None:
        self._run_id = run_id
        self._semantic = semantic

    def log_event(self, *, turn_number, agent_id, llm_response, tool_result, **kwargs):
        status = "✓" if tool_result.status == "success" else "✗"
        print(
            f"[Run {self._run_id}] Turn {turn_number:>2}: "
            f"{agent_id} {status} {llm_response.tool_name}({_fmt_args(llm_response.arguments)})"
            f"  → {tool_result.message}"
        )
        self._semantic.log_event(
            turn_number=turn_number,
            agent_id=agent_id,
            llm_response=llm_response,
            tool_result=tool_result,
            **kwargs,
        )

    def flush(self) -> str | None:
        return self._semantic.flush(run_id=self._run_id)


def _fmt_args(args: dict) -> str:
    if not args:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def run(run_id: str = "01") -> None:
    print(f"[Run {run_id}] Generating dungeon world …")
    world = generate_valid_world()

    agent_a = AgentState(agent_id="agent_a", position=world.agent_positions["agent_a"])
    agent_b = AgentState(agent_id="agent_b", position=world.agent_positions["agent_b"])

    llm_a_client = LLMClient(model_name=_MODEL_NAME, prompt_path=str(_PROMPT_PATH))
    llm_b_client = LLMClient(model_name=_MODEL_NAME, prompt_path=str(_PROMPT_PATH))

    semantic = SemanticLogger()
    logger = _CompositeLogger(run_id, semantic)

    # Wrap LLM clients with Langfuse tracing (no-op if env vars absent)
    llm_a = type("_W", (), {
        "get_decision": wrap_with_langfuse(llm_a_client, run_id, 0, "agent_a")
    })()
    llm_b = type("_W", (), {
        "get_decision": wrap_with_langfuse(llm_b_client, run_id, 0, "agent_b")
    })()

    loop = GameLoop(world, agent_a, agent_b, llm_a, llm_b, logger)

    print(f"[Run {run_id}] Starting simulation (max 50 turns) …\n")
    result = loop.run()

    print(f"\n[Run {run_id}] Simulation ended — {result.end_condition.value.upper()} at turn {result.turn_number}")
    if result.log_path:
        print(f"[Run {run_id}] Semantic log written to: {result.log_path}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else "01"
    run(run_id)
