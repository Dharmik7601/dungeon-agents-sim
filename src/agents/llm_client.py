"""LLM client — injects shadow state into the system prompt and parses JSON responses."""

import json

from google import genai

from src.agents.state import AgentState, LLMResponse, ParseError
from src.world.state import WorldState


class LLMClient:
    def __init__(self, model_name: str, prompt_path: str) -> None:
        self._model_name = model_name
        # api_key is read from GOOGLE_API_KEY env var by the SDK automatically
        self._client = genai.Client()
        with open(prompt_path, encoding="utf-8") as f:
            self._prompt_template = f.read()

    def get_decision(self, agent: AgentState, world: WorldState) -> LLMResponse:
        prompt = self._build_prompt(agent, world)
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        return self._parse_response(response.text, agent)

    # ------------------------------------------------------------------

    def _build_prompt(self, agent: AgentState, world: WorldState) -> str:
        shadow_map_str = self._format_shadow_map(agent)
        inventory_str = json.dumps(agent.inventory) if agent.inventory else "[]"
        messages_str = "\n".join(agent.message_inbox) if agent.message_inbox else "(none)"

        return (
            self._prompt_template
            .replace("{{AGENT_ID}}", agent.agent_id)
            .replace("{{TURN_NUMBER}}", str(world.turn_number))
            .replace("{{SHADOW_MAP}}", shadow_map_str)
            .replace("{{INVENTORY}}", inventory_str)
            .replace("{{MESSAGES}}", messages_str)
        )

    @staticmethod
    def _format_shadow_map(agent: AgentState) -> str:
        if not agent.shadow_map:
            return "(no cells explored yet)"
        lines = [
            f"  ({x},{y}): {cell_type.value}"
            for (x, y), cell_type in sorted(agent.shadow_map.items())
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_response(text: str, agent: AgentState) -> LLMResponse:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            agent.consecutive_parse_failures += 1
            raise ParseError(f"LLM returned non-JSON response: {exc}") from exc

        agent.consecutive_parse_failures = 0
        return LLMResponse(
            reasoning=data.get("reasoning", ""),
            expected_state=data.get("expected_state", {}),
            tool_name=data.get("tool_name", ""),
            arguments=data.get("arguments", {}),
        )
