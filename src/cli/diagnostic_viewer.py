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

def _fmt_location(loc: dict | None) -> str:
    if loc:
        return f"({loc['position'][0]}, {loc['position'][1]}) confirmed on turn {loc['turn_number']}"
    return "(unknown)"


def _fmt_input_lines(event: dict, indent: str = "  ") -> list[str]:
    """Build Input section lines shared by success and incident renders."""
    ctx = event.get("state_context", {})
    ai = ctx.get("agent_input", {})
    shadow = ctx.get("shadow_state", {})

    lines: list[str] = []
    lines.append(f"{indent}Last known location: {_fmt_location(ai.get('last_known_location'))}")
    lines.append(f"{indent}Shadow: {len(shadow)} cells observed")

    inbox = ai.get("message_inbox") or []
    lines.append(f"{indent}Inbox: {'; '.join(inbox) if inbox else '(none)'}")

    mistake = ai.get("last_mistake")
    if mistake:
        lines.append(f"{indent}Last mistake: {mistake['tool_name']} on turn {mistake['turn_number']} — {mistake['reason']}")
    else:
        lines.append(f"{indent}Last mistake: (none)")

    calls = ai.get("recent_calls") or []
    if calls:
        call_parts = []
        for c in calls:
            a = ", ".join(f"{k}={v!r}" for k, v in c.get("arguments", {}).items())
            call_parts.append(f"T{c['turn_number']}: {c['tool_name']}({a})")
        lines.append(f"{indent}Recent calls: {', '.join(call_parts)}")
    else:
        lines.append(f"{indent}Recent calls: (none)")

    return lines


def render_success(event: dict, console: Console) -> None:
    """Render a successful turn with clear Input / Output sections (dim)."""
    turn = event["turn_number"]
    agent_id = event["agent_id"]
    tool_name = event["action"]["tool_name"]
    args = event["action"].get("arguments", {})
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
    reasoning = event["state_context"]["agent_beliefs"].get("reasoning", "")

    console.print(Text(f"[Turn {turn}] {agent_id} \u2713 {tool_name}({args_str})", style="dim"))
    console.print(Text("  \u2500\u2500 Input \u2500\u2500", style="dim"))
    for line in _fmt_input_lines(event):
        console.print(Text(line, style="dim"))
    console.print(Text("  \u2500\u2500 Output \u2500\u2500", style="dim"))
    if reasoning:
        console.print(Text(f"  Reasoning: \"{reasoning}\"", style="dim italic"))


def render_incident(event: dict, console: Console) -> None:
    """Render a failed turn as a red Panel with Input / Output / Result sections."""
    turn = event["turn_number"]
    agent_id = event["agent_id"]
    tool_name = event["action"]["tool_name"]
    args = event["action"].get("arguments", {})
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
    reasoning = event["state_context"]["agent_beliefs"].get("reasoning", "")
    error_msg = event["execution_result"].get("error_message") or ""
    deltas = event["execution_result"].get("deltas", [])
    ctx = event.get("state_context", {})
    shadow = ctx.get("shadow_state", {})

    content_lines: list[str] = []

    # ── Input ────────────────────────────────────────────────────────────────
    content_lines.append("[bold]── Input ──[/bold]")
    content_lines.extend(_fmt_input_lines(event))
    if shadow:
        content_lines.append("  Shadow state:")
        for key, val in sorted(shadow.items()):
            content_lines.append(f"    {key}: {val}")
    content_lines.append("")

    # ── Output ───────────────────────────────────────────────────────────────
    content_lines.append("[bold]── Output ──[/bold]")
    content_lines.append(f"  Reasoning: [italic]{reasoning}[/italic]")
    content_lines.append(f"  Action: {tool_name}({args_str})")
    content_lines.append("")

    # ── Result ───────────────────────────────────────────────────────────────
    content_lines.append("[bold]── Result ──[/bold]")
    if error_msg:
        content_lines.append(f"  Error: {error_msg}")
    if deltas:
        content_lines.append("  State Desync Diff:")
        content_lines.append(_fmt_diff(deltas))
    else:
        content_lines.append("  State Desync Diff: (no deltas)")

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
