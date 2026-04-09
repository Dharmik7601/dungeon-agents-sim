"""Langfuse observability wrapper — records each LLM generation with full prompt I/O.

Design:
- Uses a module-level Langfuse singleton so the HTTP client is shared across all calls.
- Registers lf.flush() via atexit so pending traces survive Python-level crashes.
- Calls lf.flush() after every generation for real-time visibility on the dashboard.
- Prints a warning to stderr on initialisation failure instead of silently falling back,
  so misconfiguration is immediately visible.
- Falls back to a transparent no-op when env vars are absent.
- Uses the Langfuse v4 API: start_as_current_observation() context managers (OTel-based).
"""

import atexit
import os
import sys
from typing import Any, Callable

_client: Any = None  # module-level Langfuse singleton


def _langfuse_configured() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


def _get_client() -> Any:
    """Return the shared Langfuse client, initialising it once on first use."""
    global _client
    if _client is not None:
        return _client
    if not _langfuse_configured():
        return None
    try:
        from langfuse import Langfuse
        _client = Langfuse()
        # Flush on normal exit AND on unhandled exceptions (atexit runs for both).
        atexit.register(_client.flush)
        return _client
    except Exception as exc:
        print(f"[Langfuse] Warning: failed to initialise — {exc}", file=sys.stderr)
        return None


def wrap_with_langfuse(
    llm_client: Any,
    run_id: str,
    turn_number: int,
    agent_id: str,
) -> Callable:
    """Return a callable that wraps llm_client.get_decision with Langfuse tracing.

    If Langfuse is not configured or fails to initialise, returns the original
    method unchanged.

    Uses the Langfuse v4 API: start_as_current_observation() for both the
    parent trace span and the generation span nested inside it.
    """
    lf = _get_client()
    if lf is None:
        return llm_client.get_decision

    def _traced(agent, world):
        # Build the prompt to capture as generation input.
        try:
            prompt_input = llm_client._build_prompt(agent, world)
        except Exception:
            prompt_input = f"agent={agent.agent_id} turn={world.turn_number}"

        # Langfuse v4 API: nested context managers for trace → generation.
        with lf.start_as_current_observation(
            name="agent_turn_execution",
            as_type="span",
            metadata={
                "run_id": run_id,
                "agent_id": agent_id,
                "turn_number": world.turn_number,
            },
        ):
            with lf.start_as_current_observation(
                name="get_decision",
                as_type="generation",
                model=getattr(llm_client, "_model_name", "unknown"),
                input=prompt_input,
            ) as generation:
                try:
                    result = llm_client.get_decision(agent, world)
                    generation.update(
                        output={
                            "tool_name": result.tool_name,
                            "arguments": result.arguments,
                            "reasoning": result.reasoning,
                        },
                    )
                except Exception as exc:
                    generation.update(level="ERROR", status_message=str(exc))
                    lf.flush()
                    raise

        # Flush immediately so each generation appears on the dashboard in real time.
        lf.flush()
        return result

    return _traced


def flush_langfuse() -> None:
    """Explicitly flush any pending Langfuse data. No-op if not configured."""
    lf = _get_client()
    if lf is not None:
        lf.flush()
