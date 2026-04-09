# Project Setup

## What It Does
Establishes the Python packaging configuration, environment variable contract, and the prompt template that every LLM call depends on. Nothing in `src/` can run without this foundation in place.

## Implementation
Three configuration/template files:

1. **`pyproject.toml`** — PEP 621 package metadata with `hatchling` build backend. Runtime deps: `google-generativeai`, `langfuse`, `rich`. Dev extras: `pytest`, `pytest-cov`, `ruff`. Ruff configured at line-length 88, target py311, rules E/F/I. pytest testpaths set to `tests/`.

2. **`.env.example`** — Documents all four required environment variables (`GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) with placeholder values and inline comments explaining their purpose.

3. **`prompts/agent_system.md`** — XML-wrapped system prompt (`<system_prompt>` tags). Describes the dungeon rules, fog-of-war, one-turn message delay, and all 7 available tools. Injects runtime state via five `{{PLACEHOLDER}}` tokens. Instructs the LLM to respond strictly in JSON with `reasoning`, `expected_state`, `tool_name`, and `arguments` fields.

## Key Files
- `pyproject.toml` — package metadata, dependencies, build system, ruff config
- `.env.example` — environment variable contract (copy to `.env` and fill in values)
- `prompts/agent_system.md` — XML system prompt template with `{{AGENT_ID}}`, `{{TURN_NUMBER}}`, `{{SHADOW_MAP}}`, `{{INVENTORY}}`, `{{MESSAGES}}` placeholders

## Testing
- **Unit** — `tests/test_project_setup.py`: parse `pyproject.toml` with `tomllib` and assert runtime + dev dep names; assert `.env.example` contains all four variable names; assert prompt file contains `<system_prompt>` tags and all five `{{...}}` tokens
- **Integration** — N/A (configuration files)
- **Edge cases** — dep names verified against exact PyPI spellings
