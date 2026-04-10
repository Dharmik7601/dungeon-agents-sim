"""Single-run analysis — prints a statistical summary of one run_*.json log."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_events(path: Path) -> list[dict]:
    """Read and parse a semantic log file. Exits with an error message on failure."""
    if not path.exists():
        print(f"Error: log file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Metric A — Run Outcome & Duration
# ---------------------------------------------------------------------------

def derive_end_condition(events: list[dict]) -> str:
    """Classify the run as SUCCESS, TURN_LIMIT, or OTHER from the final event's ground truth."""
    gt = events[-1]["state_context"].get("ground_truth", {})

    # Find any unlocked exit cell
    exit_pos = None
    for key, val in gt.items():
        if val == "exit_unlocked" and key.startswith("cell_status_"):
            _, _, x, y = key.split("_")
            exit_pos = [int(x), int(y)]
            break

    if exit_pos is not None:
        a_pos = gt.get("agent_a_position")
        b_pos = gt.get("agent_b_position")
        if a_pos == exit_pos and b_pos == exit_pos:
            return "SUCCESS"

    last_turn = events[-1]["turn_number"]
    if last_turn >= 50:
        return "TURN_LIMIT"

    return "OTHER"


def compute_run_summary(events: list[dict]) -> dict:
    """Return outcome, total turns, exit/key positions, and Manhattan distances."""
    gt = events[-1]["state_context"].get("ground_truth", {})

    end_condition = derive_end_condition(events)
    total_turns = events[-1]["turn_number"]

    a_pos = gt.get("agent_a_position")
    b_pos = gt.get("agent_b_position")

    # Locate exit cell (locked or unlocked)
    exit_pos = None
    for key, val in gt.items():
        if val in ("exit_locked", "exit_unlocked") and key.startswith("cell_status_"):
            _, _, x, y = key.split("_")
            exit_pos = [int(x), int(y)]
            break

    def manhattan(p1, p2):
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    dist_a_to_exit = manhattan(a_pos, exit_pos) if (a_pos and exit_pos) else None
    dist_b_to_exit = manhattan(b_pos, exit_pos) if (b_pos and exit_pos) else None

    # Locate key if still on the ground
    key_pos = None
    for key, val in gt.items():
        if val == "key" and key.startswith("cell_status_"):
            _, _, x, y = key.split("_")
            key_pos = [int(x), int(y)]
            break

    dist_a_to_key = manhattan(a_pos, key_pos) if (a_pos and key_pos) else None
    dist_b_to_key = manhattan(b_pos, key_pos) if (b_pos and key_pos) else None

    return {
        "end_condition": end_condition,
        "total_turns": total_turns,
        "exit_pos": exit_pos,
        "agent_a_final": a_pos,
        "agent_b_final": b_pos,
        "dist_a_to_exit": dist_a_to_exit,
        "dist_b_to_exit": dist_b_to_exit,
        "key_pos": key_pos,
        "dist_a_to_key": dist_a_to_key,
        "dist_b_to_key": dist_b_to_key,
    }


def render_run_summary(summary: dict, console: Console) -> None:
    """Print section A — Run Outcome & Duration as a rich table."""
    ec = summary["end_condition"]
    ec_style = "green bold" if ec == "SUCCESS" else "red bold" if ec == "TURN_LIMIT" else "yellow bold"

    table = Table(title="A. Run Outcome & Duration", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("End State", f"[{ec_style}]{ec}[/{ec_style}]")
    table.add_row("Total Turns", str(summary["total_turns"]))

    if summary["end_condition"] != "SUCCESS":
        exit_str = str(summary["exit_pos"]) if summary["exit_pos"] else "unknown"
        table.add_row("Exit Cell", exit_str)
        if summary["dist_a_to_exit"] is not None:
            table.add_row("Agent A → Exit (Manhattan)", str(summary["dist_a_to_exit"]))
        if summary["dist_b_to_exit"] is not None:
            table.add_row("Agent B → Exit (Manhattan)", str(summary["dist_b_to_exit"]))
        if summary["key_pos"] is not None:
            table.add_row("Key Still On Ground", str(summary["key_pos"]))
            if summary["dist_a_to_key"] is not None:
                table.add_row("Agent A → Key (Manhattan)", str(summary["dist_a_to_key"]))
            if summary["dist_b_to_key"] is not None:
                table.add_row("Agent B → Key (Manhattan)", str(summary["dist_b_to_key"]))

    console.print(table)


# ---------------------------------------------------------------------------
# Metric B — Agent Efficiency
# ---------------------------------------------------------------------------

def compute_agent_efficiency(events: list[dict]) -> dict[str, dict]:
    """Return per-agent tool counts, total actions, failure count, error rate, and chatter."""
    data: dict[str, dict] = {}

    for event in events:
        agent = event["agent_id"]
        tool = event["action"]["tool_name"]
        status = event["execution_result"]["status"]

        if agent not in data:
            data[agent] = {
                "tool_counts": Counter(),
                "total_actions": 0,
                "failure_count": 0,
                "chatter": 0,
            }

        data[agent]["tool_counts"][tool] += 1
        data[agent]["total_actions"] += 1
        if status == "failure":
            data[agent]["failure_count"] += 1
        if tool == "send_message":
            data[agent]["chatter"] += 1

    for agent_data in data.values():
        total = agent_data["total_actions"]
        agent_data["error_rate"] = (agent_data["failure_count"] / total * 100) if total else 0.0

    return data


def render_agent_efficiency(efficiency: dict[str, dict], console: Console) -> None:
    """Print section B — Agent Efficiency as rich tables, one per agent."""
    for agent_id, data in sorted(efficiency.items()):
        table = Table(
            title=f"B. Agent Efficiency — {agent_id}",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Tool", style="dim")
        table.add_column("Count", justify="right")

        for tool, count in sorted(data["tool_counts"].items()):
            table.add_row(tool, str(count))

        table.add_section()
        table.add_row("Total actions", str(data["total_actions"]))
        table.add_row("Failures", str(data["failure_count"]))
        table.add_row("Error rate", f"{data['error_rate']:.1f}%")
        table.add_row("Chatter (send_message)", str(data["chatter"]))

        console.print(table)
        console.print()


# ---------------------------------------------------------------------------
# Metric C — Delusion Timeline
# ---------------------------------------------------------------------------

def compute_delusion_timeline(events: list[dict]) -> list[dict]:
    """Return a chronological list of delta records with time-to-correction for cell keys."""
    # Build per-agent ordered event list for forward-scan
    agent_events: dict[str, list[dict]] = {}
    for event in events:
        agent = event["agent_id"]
        agent_events.setdefault(agent, []).append(event)

    records: list[dict] = []
    for event in events:
        deltas = event["execution_result"].get("deltas") or []
        if not deltas:
            continue

        turn = event["turn_number"]
        agent = event["agent_id"]
        subsequent = [e for e in agent_events[agent] if e["turn_number"] > turn]

        for delta in deltas:
            prop = delta["property_key"]
            actual = delta["actual_value"]

            # Time-to-correction only for cell_status_X_Y keys
            if prop.startswith("cell_status_"):
                corrected_in = "never"
                for future in subsequent:
                    shadow = future["state_context"].get("shadow_state", {})
                    if shadow.get(prop) == actual:
                        corrected_in = future["turn_number"] - turn
                        break
            else:
                corrected_in = None

            records.append({
                "turn": turn,
                "agent_id": agent,
                "property_key": prop,
                "expected_value": delta["expected_value"],
                "actual_value": actual,
                "discrepancy_source": delta["discrepancy_source"],
                "corrected_in": corrected_in,
            })

    return records


def render_delusion_timeline(timeline: list[dict], console: Console) -> None:
    """Print section C — Delusion Timeline as a rich table."""
    if not timeline:
        console.print("[dim]C. Delusion Timeline — no state desyncs recorded[/dim]")
        return

    table = Table(title="C. Delusion Timeline", show_header=True, box=None, padding=(0, 2))
    table.add_column("Turn", justify="right", style="dim")
    table.add_column("Agent")
    table.add_column("Property")
    table.add_column("Expected")
    table.add_column("Actual")
    table.add_column("Source")
    table.add_column("Corrected In")

    for rec in timeline:
        corr = rec["corrected_in"]
        if corr is None:
            corr_str = "N/A"
        elif corr == "never":
            corr_str = "[red]never[/red]"
        else:
            corr_str = f"{corr} turns"

        table.add_row(
            str(rec["turn"]),
            rec["agent_id"],
            rec["property_key"],
            str(rec["expected_value"]),
            str(rec["actual_value"]),
            rec["discrepancy_source"],
            corr_str,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Metric D — Map Coverage
# ---------------------------------------------------------------------------

def compute_map_coverage(events: list[dict]) -> dict:
    """Return observed cell count and coverage % from the union of both agents' final shadow states."""
    # Find last event per agent
    last_shadow: dict[str, dict] = {}
    for event in events:
        agent = event["agent_id"]
        last_shadow[agent] = event["state_context"].get("shadow_state", {})

    observed: set[str] = set()
    for shadow in last_shadow.values():
        for key in shadow:
            if key.startswith("cell_status_"):
                observed.add(key)

    total = 64
    return {
        "observed": len(observed),
        "total": total,
        "pct": len(observed) / total * 100,
    }


def render_map_coverage(coverage: dict, console: Console) -> None:
    """Print section D — Map Coverage as a rich table."""
    table = Table(title="D. Map Coverage", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("Cells observed (union)", str(coverage["observed"]))
    table.add_row("Total cells", str(coverage["total"]))
    table.add_row("Coverage", f"{coverage['pct']:.1f}%")

    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print a statistical summary of a single dungeon-agents-sim run log."
    )
    parser.add_argument("--log-file", required=True, help="Path to run_*.json semantic log")
    args = parser.parse_args(argv)

    path = Path(args.log_file)
    events = load_events(path)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    console = Console(legacy_windows=False)
    console.print(f"Analysis: {path.name} - {len(events)} events")
    console.rule()

    summary = compute_run_summary(events)
    render_run_summary(summary, console)
    console.rule()

    efficiency = compute_agent_efficiency(events)
    render_agent_efficiency(efficiency, console)
    console.rule()

    timeline = compute_delusion_timeline(events)
    render_delusion_timeline(timeline, console)
    console.rule()

    coverage = compute_map_coverage(events)
    render_map_coverage(coverage, console)


if __name__ == "__main__":
    main()
