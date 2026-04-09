"""Tests for project-setup: requirements files, pyproject.toml tool config, .env.example, prompts/agent_system.md."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _parse_req_names(lines: list[str]) -> list[str]:
    """Extract bare package names from requirements file lines."""
    names = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        # strip version specifiers (>=, ==, ~=, !=, <, >)
        for sep in (">=", "==", "~=", "!=", "<=", "<", ">"):
            line = line.split(sep)[0]
        names.append(line.strip())
    return names


def test_requirements_runtime_deps():
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    names = _parse_req_names(lines)
    assert "google-genai" in names
    assert "langfuse" in names
    assert "rich" in names


def test_requirements_dev_deps():
    lines = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    names = _parse_req_names(lines)
    assert "pytest" in names
    assert "pytest-cov" in names
    assert "ruff" in names


def test_requirements_dev_includes_runtime():
    """requirements-dev.txt must reference requirements.txt via -r."""
    content = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in content


def test_pyproject_ruff_config():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    ruff = data["tool"]["ruff"]
    assert ruff["line-length"] == 88
    assert "py311" in ruff["target-version"]


def test_env_contains_all_vars():
    content = (ROOT / ".env").read_text()
    for var in ("GOOGLE_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        assert var in content, f"Missing variable: {var}"


def test_system_prompt_xml_structure():
    content = (ROOT / "prompts" / "agent_system.md").read_text()
    assert "<system_prompt>" in content
    assert "</system_prompt>" in content


def test_system_prompt_placeholders():
    content = (ROOT / "prompts" / "agent_system.md").read_text()
    for token in ("{{AGENT_ID}}", "{{TURN_NUMBER}}", "{{SHADOW_MAP}}", "{{INVENTORY}}", "{{MESSAGES}}"):
        assert token in content, f"Missing placeholder: {token}"
