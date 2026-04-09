"""Diagnostic viewer — renders a run_*.json semantic log in the terminal using rich."""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from src.cli.board_renderer import board_legend, render_board_from_snapshot


# ---------------------------------------------------------------------------
# Delta formatting
# ---------------------------------------------------------------------------

def _fmt_diff(deltas: list[dict]) -> str:
    """Format a list of delta dicts into a human-readable diff string."""
    if not deltas:
        return ""
    lines: list[str] = []
    for delta in deltas:
        key = delta["property_key"]
        expected = delta["expected_value"]
        actual = delta["actual_value"]
        source = delta["discrepancy_source"]
        lines.append(f"  EXPECTED: {key} = {expected!r}")
        lines.append(f"  ACTUAL:   {key} = {actual!r}")
        lines.append(f"  Source: {source}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_success(event: dict, console: Console) -> None:
    """Render a successful turn as a dim entry with reasoning."""
    turn = event["turn_number"]
    agent_id = event["agent_id"]
    tool_name = event["action"]["tool_name"]
    args = event["action"].get("arguments", {})
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
    reasoning = event["state_context"]["agent_beliefs"].get("reasoning", "")
    console.print(Text(f"[Turn {turn}] {agent_id} \u2713 {tool_name}({args_str})", style="dim"))
    if reasoning:
        console.print(Text(f"  \"{reasoning}\"", style="dim italic"))


def render_incident(event: dict, console: Console) -> None:
    """Render a failed turn as a high-visibility red Incident Block Panel."""
    turn = event["turn_number"]
    agent_id = event["agent_id"]
    tool_name = event["action"]["tool_name"]
    args = event["action"].get("arguments", {})
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
    reasoning = event["state_context"]["agent_beliefs"].get("reasoning", "")
    deltas = event["execution_result"].get("deltas", [])

    # Build panel content
    content_lines: list[str] = []

    # Section 1 — What Happened
    content_lines.append("[bold]What Happened[/bold]")
    content_lines.append(f"  {tool_name}({args_str})")
    content_lines.append("")

    # Section 2 — State Desync Diff
    content_lines.append("[bold]State Desync Diff[/bold]")
    if deltas:
        content_lines.append(_fmt_diff(deltas))
    else:
        content_lines.append("  (no deltas)")
    content_lines.append("")

    # Section 3 — Agent Reasoning
    content_lines.append("[bold]Agent Reasoning[/bold]")
    content_lines.append(f"  [italic]{reasoning}[/italic]")

    body = "\n".join(content_lines)
    panel = Panel(
        body,
        title=f"[red bold]INCIDENT — Turn {turn} | {agent_id}[/red bold]",
        border_style="red",
    )
    console.print(panel)


# ---------------------------------------------------------------------------
# Log renderer
# ---------------------------------------------------------------------------

def render_log(
    events: list[dict],
    filter_mode: str,
    agent_filter: str | None,
    console: Console,
) -> None:
    """Iterate events and render each one according to filter settings."""
    for event in events:
        if agent_filter and event["agent_id"] != agent_filter:
            continue
        status = event["execution_result"]["status"]
        if filter_mode == "failures_only" and status != "failure":
            continue

        # Board state at this moment in the replay
        ground_truth = event.get("state_context", {}).get("ground_truth", {})
        if ground_truth:
            console.print(render_board_from_snapshot(ground_truth))
            console.print(board_legend())
            console.print(Rule(style="dim"))

        if status == "failure":
            render_incident(event, console)
        else:
            render_success(event, console)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Render a dungeon-agents-sim semantic log as a terminal timeline."
    )
    parser.add_argument("--log-file", required=True, help="Path to run_*.json semantic log")
    parser.add_argument(
        "--filter",
        dest="filter_mode",
        choices=["all", "failures_only"],
        default="all",
        help="Show all events or only failures (default: all)",
    )
    parser.add_argument(
        "--agent",
        dest="agent_filter",
        choices=["agent_a", "agent_b"],
        default=None,
        help="Restrict output to one agent",
    )
    args = parser.parse_args(argv)

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Error: log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    try:
        events: list[dict] = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {log_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    console = Console()
    render_log(events, filter_mode=args.filter_mode, agent_filter=args.agent_filter, console=console)


if __name__ == "__main__":
    main()
