"""Game loop orchestrator — sequential turn execution with end-condition checking."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.agents.state import AgentState, LLMResponse, ParseError
from src.agents.tools import ToolDispatcher
from src.world.state import WorldState


class EndCondition(Enum):
    SUCCESS = "success"
    TURN_LIMIT = "turn_limit"
    ACTION_DEADLOCK = "action_deadlock"
    PARSE_DEADLOCK = "parse_deadlock"


@dataclass
class RunResult:
    end_condition: EndCondition
    turn_number: int
    log_path: str | None


class GameLoop:
    def __init__(
        self,
        world: WorldState,
        agent_a: AgentState,
        agent_b: AgentState,
        llm_a: Any,
        llm_b: Any,
        logger: Any,
        max_turns: int = 50,
    ) -> None:
        self._world = world
        self._agent_a = agent_a
        self._agent_b = agent_b
        self._llm_a = llm_a
        self._llm_b = llm_b
        self._logger = logger
        self._max_turns = max_turns

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> RunResult:
        if self._check_success():
            return RunResult(EndCondition.SUCCESS, self._world.turn_number, None)

        while self._world.turn_number < self._max_turns:
            # Deliver messages from the previous round to each agent
            self._deliver_messages(self._agent_a, self._agent_b)
            self._deliver_messages(self._agent_b, self._agent_a)

            # Agent A acts
            end = self._run_agent_turn(self._agent_a, self._llm_a, self._agent_b)
            if end:
                return RunResult(end, self._world.turn_number, self._flush_logger())
            if self._check_success():
                return RunResult(EndCondition.SUCCESS, self._world.turn_number, self._flush_logger())

            # Agent B acts
            end = self._run_agent_turn(self._agent_b, self._llm_b, self._agent_a)
            if end:
                return RunResult(end, self._world.turn_number, self._flush_logger())
            if self._check_success():
                return RunResult(EndCondition.SUCCESS, self._world.turn_number, self._flush_logger())

            self._world.turn_number += 1

        return RunResult(EndCondition.TURN_LIMIT, self._world.turn_number, self._flush_logger())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_agent_turn(
        self,
        agent: AgentState,
        llm: Any,
        partner: AgentState,
    ) -> EndCondition | None:
        # Get LLM decision
        try:
            response: LLMResponse = llm.get_decision(agent, self._world)
        except ParseError as exc:
            agent.last_mistake = {
                "tool_name": "(parse_error)",
                "turn_number": self._world.turn_number,
                "reason": str(exc),
            }
            if agent.consecutive_parse_failures >= 3:
                return EndCondition.PARSE_DEADLOCK
            return None

        # Snapshot shadow state before action (for tracing)
        shadow_snapshot = dict(agent.shadow_map)

        # Execute tool
        result = ToolDispatcher.dispatch(
            response.tool_name, response.arguments, agent, self._world
        )

        # Track recent calls (max 5 sliding window)
        agent.recent_calls.append({
            "tool_name": response.tool_name,
            "arguments": response.arguments,
            "turn_number": self._world.turn_number,
        })
        if len(agent.recent_calls) > 5:
            agent.recent_calls.pop(0)

        # Record mistake on failure
        if result.status == "failure":
            agent.last_mistake = {
                "tool_name": response.tool_name,
                "turn_number": self._world.turn_number,
                "reason": result.message,
            }

        # Log event
        self._logger.log_event(
            turn_number=self._world.turn_number,
            agent_id=agent.agent_id,
            llm_response=response,
            shadow_state_before=shadow_snapshot,
            tool_result=result,
            world=self._world,
        )

        # Check action deadlock
        if agent.consecutive_invalid_actions >= 5:
            return EndCondition.ACTION_DEADLOCK

        return None

    def _deliver_messages(self, agent: AgentState, partner: AgentState) -> None:
        """Move partner's outbox into agent's inbox (one-turn delay)."""
        agent.message_inbox = list(partner.message_outbox)
        partner.message_outbox.clear()

    def _check_success(self) -> bool:
        exit_pos = self._world.exit_pos
        a_at_exit = self._agent_a.position == exit_pos
        b_at_exit = self._agent_b.position == exit_pos
        return a_at_exit and b_at_exit and not self._world.exit_locked

    def _flush_logger(self) -> str | None:
        if hasattr(self._logger, "flush"):
            return self._logger.flush()
        return None
