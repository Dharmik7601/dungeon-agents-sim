"""Cross-run analysis — aggregate behavioral trends across a directory of run_*.json logs."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.cli.single_run_analysis import compute_map_coverage, derive_end_condition


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_all_runs(directory: Path) -> list[list[dict]]:
    """Load all run_*.json files in directory. Exits if none found."""
    files = sorted(directory.glob("run_*.json"))
    if not files:
        print(f"Error: no run_*.json files found in {directory}", file=sys.stderr)
        sys.exit(1)
    runs = []
    for f in files:
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"Warning: skipping {f.name} — invalid JSON: {exc}", file=sys.stderr)
    return runs


# ---------------------------------------------------------------------------
# Metric A — Global Run Outcomes
# ---------------------------------------------------------------------------

def compute_global_outcomes(runs: list[list[dict]]) -> dict:
    """Return success rate, avg completion turns, and failure type distribution."""
    success_turns = []
    turn_limit_count = 0
    other_count = 0

    for events in runs:
        ec = derive_end_condition(events)
        if ec == "SUCCESS":
            success_turns.append(events[-1]["turn_number"])
        elif ec == "TURN_LIMIT":
            turn_limit_count += 1
        else:
            other_count += 1

    total = len(runs)
    success_count = len(success_turns)
    return {
        "total_runs": total,
        "success_count": success_count,
        "success_rate": success_count / total * 100 if total else 0.0,
        "avg_completion_turns": sum(success_turns) / len(success_turns) if success_turns else None,
        "turn_limit_count": turn_limit_count,
        "other_count": other_count,
    }


def render_global_outcomes(outcomes: dict, console: Console) -> None:
    """Print section A — Global Run Outcomes."""
    table = Table(title="A. Global Run Outcomes", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("Total runs", str(outcomes["total_runs"]))
    table.add_row("Successes", f"{outcomes['success_count']} ({outcomes['success_rate']:.1f}%)")
    avg = outcomes["avg_completion_turns"]
    table.add_row("Avg turns to success", f"{avg:.1f}" if avg is not None else "N/A")
    table.add_row("Turn-limit failures", str(outcomes["turn_limit_count"]))
    table.add_row("Other early stops", str(outcomes["other_count"]))

    console.print(table)


# ---------------------------------------------------------------------------
# Metric B — Top Failure Drivers
# ---------------------------------------------------------------------------

def compute_top_failure_drivers(runs: list[list[dict]]) -> list[tuple[str, int]]:
    """Return top-5 failure reasons by frequency across all runs."""
    counter: Counter = Counter()

    for events in runs:
        for event in events:
            if event["execution_result"]["status"] != "failure":
                continue
            deltas = event["execution_result"].get("deltas") or []
            if deltas:
                for delta in deltas:
                    counter[delta["property_key"]] += 1
            else:
                msg = event["execution_result"].get("error_message") or "unknown"
                counter[msg] += 1

    return counter.most_common(5)


def render_top_failure_drivers(drivers: list[tuple[str, int]], console: Console) -> None:
    """Print section B — Top Failure Drivers."""
    if not drivers:
        console.print("[dim]B. Top Failure Drivers — no failures recorded[/dim]")
        return

    table = Table(title="B. Top Failure Drivers", show_header=True, box=None, padding=(0, 2))
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Reason")
    table.add_column("Count", justify="right")

    for rank, (reason, count) in enumerate(drivers, 1):
        table.add_row(str(rank), reason, str(count))

    console.print(table)


# ---------------------------------------------------------------------------
# Metric C — Stubbornness Index
# ---------------------------------------------------------------------------

def compute_stubborn_failures(runs: list[list[dict]]) -> dict:
    """Return count and % of failures that immediately repeat a failed action (same agent, same tool+args)."""
    total_failures = 0
    stubborn_count = 0

    for events in runs:
        # Build per-agent ordered event list
        agent_events: dict[str, list[dict]] = {}
        for event in events:
            agent_events.setdefault(event["agent_id"], []).append(event)

        for agent_evs in agent_events.values():
            for i in range(1, len(agent_evs)):
                prev = agent_evs[i - 1]
                curr = agent_evs[i]
                if prev["execution_result"]["status"] == "failure":
                    total_failures += 1
                    if (curr["execution_result"]["status"] == "failure"
                            and curr["action"]["tool_name"] == prev["action"]["tool_name"]
                            and curr["action"]["arguments"] == prev["action"]["arguments"]):
                        stubborn_count += 1
            # Count the last event's failure if it is one
            if agent_evs and agent_evs[-1]["execution_result"]["status"] == "failure":
                total_failures += 1

    return {
        "stubborn_count": stubborn_count,
        "total_failures": total_failures,
        "pct": stubborn_count / total_failures * 100 if total_failures else 0.0,
    }


def render_stubborn_failures(stubbornness: dict, console: Console) -> None:
    """Print section C — Stubbornness Index."""
    table = Table(title="C. Stubbornness Index", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    table.add_row("Total failures", str(stubbornness["total_failures"]))
    table.add_row("Stubborn repeats", str(stubbornness["stubborn_count"]))
    table.add_row("Stubbornness rate", f"{stubbornness['pct']:.1f}%")

    console.print(table)


# ---------------------------------------------------------------------------
# Metric D — Tool Reliability
# ---------------------------------------------------------------------------

def compute_tool_reliability(runs: list[list[dict]]) -> dict[str, dict]:
    """Return per-tool total executions, failure count, and failure rate % across all runs."""
    totals: Counter = Counter()
    failures: Counter = Counter()

    for events in runs:
        for event in events:
            tool = event["action"]["tool_name"]
            totals[tool] += 1
            if event["execution_result"]["status"] == "failure":
                failures[tool] += 1

    return {
        tool: {
            "total": totals[tool],
            "failures": failures[tool],
            "failure_rate": failures[tool] / totals[tool] * 100 if totals[tool] else 0.0,
        }
        for tool in totals
    }


def render_tool_reliability(reliability: dict[str, dict], console: Console) -> None:
    """Print section D — Tool Reliability."""
    table = Table(title="D. Tool Reliability", show_header=True, box=None, padding=(0, 2))
    table.add_column("Tool")
    table.add_column("Total", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Failure Rate", justify="right")

    for tool, data in sorted(reliability.items()):
        rate = data["failure_rate"]
        rate_str = f"[red]{rate:.1f}%[/red]" if rate > 20 else f"{rate:.1f}%"
        table.add_row(tool, str(data["total"]), str(data["failures"]), rate_str)

    console.print(table)


# ---------------------------------------------------------------------------
# Metric E — Average Exploration Density
# ---------------------------------------------------------------------------

def compute_avg_exploration_density(runs: list[list[dict]]) -> dict:
    """Return per-run coverage % and their mean across all runs."""
    per_run = [compute_map_coverage(events)["pct"] for events in runs]
    avg = sum(per_run) / len(per_run) if per_run else 0.0
    return {"per_run": per_run, "avg_pct": avg}


def render_avg_exploration_density(density: dict, console: Console) -> None:
    """Print section E — Average Exploration Density."""
    table = Table(title="E. Average Exploration Density", show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value")

    for i, pct in enumerate(density["per_run"], 1):
        table.add_row(f"Run {i} coverage", f"{pct:.1f}%")
    table.add_section()
    table.add_row("Average coverage", f"{density['avg_pct']:.1f}%")

    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate analysis across all run_*.json logs in a directory."
    )
    parser.add_argument(
        "--dir",
        default="saved_logs",
        help="Directory containing run_*.json files (default: saved_logs/)",
    )
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    runs = load_all_runs(directory)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    console = Console(legacy_windows=False)
    console.print(f"Cross-run analysis: {directory} - {len(runs)} runs")
    console.rule()

    outcomes = compute_global_outcomes(runs)
    render_global_outcomes(outcomes, console)
    console.rule()

    drivers = compute_top_failure_drivers(runs)
    render_top_failure_drivers(drivers, console)
    console.rule()

    stubbornness = compute_stubborn_failures(runs)
    render_stubborn_failures(stubbornness, console)
    console.rule()

    reliability = compute_tool_reliability(runs)
    render_tool_reliability(reliability, console)
    console.rule()

    density = compute_avg_exploration_density(runs)
    render_avg_exploration_density(density, console)


if __name__ == "__main__":
    main()
