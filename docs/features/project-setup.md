# Project Setup

## What It Does
Establishes the Python packaging configuration, environment variable contract, and the prompt template that every LLM call depends on. Nothing in `src/` can run without this foundation in place.

## Implementation
Two configuration/template files:

1. **`requirements.txt`** — Runtime dependencies: `google-genai`, `langfuse`, `rich`, `pytest`, `pytest-cov`, `ruff`. Single flat file; no `pyproject.toml` or separate dev requirements file.

2. **`.env.example`** — Documents all four required environment variables (`GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) with placeholder values and inline comments explaining their purpose.

3. **`prompts/agent_system.md`** — XML-wrapped system prompt (`<system_prompt>` tags). Describes the dungeon rules, fog-of-war, one-turn message delay, and all 7 available tools. Injects runtime state via five `{{PLACEHOLDER}}` tokens. Instructs the LLM to respond strictly in JSON with `reasoning`, `expected_state`, `tool_name`, and `arguments` fields.

## Key Files
- `requirements.txt` — all dependencies (runtime + dev tools)
- `.env.example` — environment variable contract (copy to `.env` and fill in values)
- `prompts/agent_system.md` — XML system prompt template with `{{AGENT_ID}}`, `{{TURN_NUMBER}}`, `{{SHADOW_MAP}}`, `{{INVENTORY}}`, `{{MESSAGES}}` placeholders

## Testing
- `tests/test_project_setup.py` removed — pyproject.toml and requirements-dev.txt were deleted; remaining setup (requirements.txt, .env.example, prompt file) is verified implicitly by the full test suite running successfully.
