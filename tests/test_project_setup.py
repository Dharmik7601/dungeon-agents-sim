"""Tests for project-setup: pyproject.toml, .env.example, prompts/agent_system.md."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_pyproject_runtime_deps():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    deps = data["project"]["dependencies"]
    dep_names = [d.split(">=")[0].split("==")[0].strip() for d in deps]
    assert "google-genai" in dep_names
    assert "langfuse" in dep_names
    assert "rich" in dep_names


def test_pyproject_dev_deps():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    dev_deps = data["project"]["optional-dependencies"]["dev"]
    dep_names = [d.split(">=")[0].split("==")[0].strip() for d in dev_deps]
    assert "pytest" in dep_names
    assert "pytest-cov" in dep_names
    assert "ruff" in dep_names


def test_pyproject_ruff_config():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    ruff = data["tool"]["ruff"]
    assert ruff["line-length"] == 88
    assert "py311" in ruff["target-version"]


def test_env_example_contains_all_vars():
    content = (ROOT / ".env.example").read_text()
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
