"""Langfuse observability wrapper — tags each LLM call with run metadata.

Falls back to a transparent no-op if Langfuse is not configured (missing env vars
or package not callable), so local runs and tests work without a Langfuse account.
"""

import os
from typing import Any, Callable


def wrap_with_langfuse(
    llm_client: Any,
    run_id: str,
    turn_number: int,
    agent_id: str,
) -> Callable:
    """Return a callable that wraps llm_client.get_decision with Langfuse tracing.

    If Langfuse is not configured the returned callable is a transparent pass-through.
    """
    if not _langfuse_configured():
        return llm_client.get_decision

    try:
        from langfuse.decorators import langfuse_context, observe

        @observe(name="agent_turn_execution")
        def _traced(agent, world):
            langfuse_context.update_current_trace(
                metadata={
                    "run_id": run_id,
                    "turn_number": turn_number,
                    "agent_id": agent_id,
                }
            )
            return llm_client.get_decision(agent, world)

        return _traced

    except Exception:
        # Any import or configuration failure → silent fallback
        return llm_client.get_decision


def _langfuse_configured() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )
