"""Streamlit observability dashboard for dungeon-agents-sim."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports resolve whether
# the script is launched via `streamlit run src/cli/streamlit_app.py` from the
# project root locally, or from an arbitrary working directory on Streamlit Cloud.
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ---------------------------------------------------------------------------
# Cell display constants (mirrors board_renderer.py)
# ---------------------------------------------------------------------------

_CELL_SYMBOL: dict[str, str] = {
    "empty":          "·",
    "wall":           "█",
    "key":            "K",
    "exit_locked":    "X",
    "exit_unlocked":  "O",
}

_CELL_COLOR: dict[str, str] = {
    "empty":          "#555555",
    "wall":           "#dddddd",
    "key":            "#f0c040",
    "exit_locked":    "#e05050",
    "exit_unlocked":  "#50c878",
}

_FOG_SYMBOL = "?"
_FOG_COLOR  = "#333333"

_AGENT_A_COLOR  = "#00bcd4"   # cyan
_AGENT_B_COLOR  = "#5c6bc0"   # blue
_BOTH_COLOR     = "#ce93d8"   # magenta


# ---------------------------------------------------------------------------
# Task 2 — HTML grid renderer (pure function, no Streamlit dependency)
# ---------------------------------------------------------------------------

def render_html_grid(
    grid_data: dict,
    agent_positions: dict,
    width: int,
    height: int,
    shadow_filter: set | None = None,
) -> str:
    """Return a CSS-styled HTML table string for the dungeon grid.

    Args:
        grid_data: Mapping of ``cell_status_X_Y`` keys to cell-type strings.
        agent_positions: Dict with optional keys ``"agent_a"`` and ``"agent_b"``,
            each mapping to an ``[x, y]`` list.
        width: Grid width in cells.
        height: Grid height in cells.
        shadow_filter: If a ``set`` is provided, cells whose ``cell_status_X_Y``
            key is *absent* from the set are rendered as fog of war (``?``).
            Pass ``None`` (default) to show all cells.

    Returns:
        An HTML string containing a ``<table>`` element.
    """
    pos_a = tuple(agent_positions["agent_a"]) if "agent_a" in agent_positions else None
    pos_b = tuple(agent_positions["agent_b"]) if "agent_b" in agent_positions else None

    cell_style = (
        "width:28px;height:28px;text-align:center;vertical-align:middle;"
        "font-size:14px;font-weight:bold;border:1px solid #222;"
    )

    rows: list[str] = []
    for y in range(height):
        cells: list[str] = []
        for x in range(width):
            key = f"cell_status_{x}_{y}"
            coord = (x, y)

            # Agent overlay takes priority
            both = (coord == pos_a and coord == pos_b)
            only_a = (coord == pos_a and coord != pos_b)
            only_b = (coord == pos_b and coord != pos_a)

            if both:
                symbol = "✦"
                color  = _BOTH_COLOR
            elif only_a:
                symbol = "A"
                color  = _AGENT_A_COLOR
            elif only_b:
                symbol = "B"
                color  = _AGENT_B_COLOR
            else:
                # Fog-of-war check
                if shadow_filter is not None and key not in shadow_filter:
                    symbol = _FOG_SYMBOL
                    color  = _FOG_COLOR
                else:
                    cell_val = grid_data.get(key, "empty")
                    symbol = _CELL_SYMBOL.get(cell_val, "?")
                    color  = _CELL_COLOR.get(cell_val, _FOG_COLOR)

            cells.append(
                f'<td style="{cell_style}background:{color};color:#fff;">{symbol}</td>'
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    table_style = "border-collapse:collapse;font-family:monospace;"
    return f'<table style="{table_style}">{"".join(rows)}</table>'


# ---------------------------------------------------------------------------
# Task 3 — list_log_files helper
# ---------------------------------------------------------------------------

def list_log_files(directory: Path) -> list[Path]:
    """Return sorted ``run_*.json`` paths in *directory*, excluding WIP files."""
    return sorted(
        p for p in directory.glob("run_*.json")
        if not p.name.startswith("run_wip_")
    )


# ---------------------------------------------------------------------------
# Streamlit app entry point (Tasks 3-6)
# ---------------------------------------------------------------------------

def main() -> None:
    import streamlit as st
    import pandas as pd
    import plotly.graph_objects as go

    from src.cli.single_run_analysis import (
        compute_run_summary,
        compute_agent_efficiency,
        compute_delusion_timeline,
        compute_map_coverage,
    )
    from src.cli.cross_run_analysis import (
        compute_global_outcomes,
        compute_top_failure_drivers,
        compute_stubborn_failures,
        compute_tool_reliability,
        compute_avg_exploration_density,
    )

    st.set_page_config(page_title="Dungeon Agents Dashboard", layout="wide")

    # ------------------------------------------------------------------
    # Sidebar — mode selection only
    # ------------------------------------------------------------------
    st.sidebar.title("Dungeon Agents")
    mode = st.sidebar.radio(
        "Mode",
        ["Interactive Replay", "Run Performance", "Global Insights"],
    )

    log_dir = Path("saved_logs")
    log_files = list_log_files(log_dir)

    # ------------------------------------------------------------------
    # Mode dispatch
    # ------------------------------------------------------------------
    if mode == "Interactive Replay":
        _render_interactive_replay(log_files)
    elif mode == "Run Performance":
        _render_run_performance(
            log_files,
            compute_run_summary,
            compute_agent_efficiency,
            compute_delusion_timeline,
            compute_map_coverage,
            pd,
        )
    else:
        _render_global_insights(
            log_dir,
            compute_global_outcomes,
            compute_top_failure_drivers,
            compute_stubborn_failures,
            compute_tool_reliability,
            compute_avg_exploration_density,
            pd,
            go,
        )


# ---------------------------------------------------------------------------
# Task 4 — Interactive Replay
# ---------------------------------------------------------------------------

def _render_interactive_replay(log_files: list[Path]) -> None:
    import streamlit as st

    st.title("Interactive Replay")

    if not log_files:
        st.warning("No run_*.json files found in `saved_logs/`. Run a simulation first.")
        return

    # Log selection at top of page
    log_names = [p.name for p in log_files]
    selected_name = st.selectbox("Log file", log_names, key="replay_log")
    selected_path = next(p for p in log_files if p.name == selected_name)
    events = json.loads(selected_path.read_text(encoding="utf-8"))

    if not events:
        st.warning("No events in this log.")
        return

    # Group events by turn number — each turn has one event per agent
    turn_events: dict[int, dict[str, dict]] = {}
    for e in events:
        t = e["turn_number"]
        turn_events.setdefault(t, {})[e["agent_id"]] = e

    unique_turns = sorted(turn_events.keys())

    # Session state: one key for the turn value, one for the text-box display.
    # Both are namespaced by log filename so switching logs resets navigation.
    state_key = f"replay_turn_{selected_name}"
    input_key = f"replay_turn_input_{selected_name}"

    if state_key not in st.session_state:
        st.session_state[state_key] = unique_turns[0]

    # Clamp in case the stored value is out of range (e.g. after switching logs)
    current = st.session_state[state_key]
    if current not in unique_turns:
        current = unique_turns[0]
        st.session_state[state_key] = current

    # Keep the text-box display in sync with the turn state
    if input_key not in st.session_state:
        st.session_state[input_key] = str(current)

    # Navigation: vertical_alignment="bottom" aligns button bottoms with the
    # input-field bottom so no &nbsp; spacer hacks are needed.
    # A wide right spacer keeps the controls left-aligned.
    col_prev, col_input, col_next, _spacer = st.columns(
        [1, 1.5, 1, 8], vertical_alignment="bottom"
    )
    with col_prev:
        if st.button("◀ Prev", use_container_width=True):
            idx = unique_turns.index(current)
            new_turn = unique_turns[max(0, idx - 1)]
            st.session_state[state_key] = new_turn
            st.session_state[input_key] = str(new_turn)
            st.rerun()
    with col_next:
        if st.button("Next ▶", use_container_width=True):
            idx = unique_turns.index(current)
            new_turn = unique_turns[min(len(unique_turns) - 1, idx + 1)]
            st.session_state[state_key] = new_turn
            st.session_state[input_key] = str(new_turn)
            st.rerun()
    def _on_turn_input() -> None:
        # Called by Streamlit before the next render — safe to write any key.
        raw = st.session_state[input_key]
        if raw.lstrip("-").isdigit():
            parsed = int(raw)
            clamped = max(unique_turns[0], min(unique_turns[-1], parsed))
            st.session_state[state_key] = clamped
            st.session_state[input_key] = str(clamped)
        else:
            # Non-numeric: reset box to current valid turn
            st.session_state[input_key] = str(st.session_state[state_key])

    with col_input:
        st.text_input(
            f"Turn (0 – {unique_turns[-1]})",
            key=input_key,
            on_change=_on_turn_input,
        )

    current_turn = st.session_state[state_key]
    evts_at_turn = turn_events.get(current_turn, {})
    event_a = evts_at_turn.get("agent_a")
    event_b = evts_at_turn.get("agent_b")

    # Ground truth: agent_a acts first so its snapshot is earlier; fall back to B
    gt_event = event_a or event_b
    gt = gt_event.get("state_context", {}).get("ground_truth", {}) if gt_event else {}
    width  = gt.get("grid_width", 8)
    height = gt.get("grid_height", 8)
    agent_positions = {
        "agent_a": gt.get("agent_a_position", [-1, -1]),
        "agent_b": gt.get("agent_b_position", [-1, -1]),
    }

    # Shadow filters — one set per agent from their own event's shadow_state
    def _shadow_keys(evt: dict | None) -> set:
        if evt is None:
            return set()
        return {
            k for k in evt.get("state_context", {}).get("shadow_state", {})
            if k.startswith("cell_status_")
        }

    shadow_a = _shadow_keys(event_a)
    shadow_b = _shadow_keys(event_b)

    # ------------------------------------------------------------------
    # Three boards side-by-side
    # ------------------------------------------------------------------
    col_gt, col_pa, col_pb = st.columns(3)
    with col_gt:
        st.subheader("Ground Truth")
        st.markdown(
            render_html_grid(gt, agent_positions, width, height),
            unsafe_allow_html=True,
        )
    with col_pa:
        st.subheader("Agent A Perspective")
        if event_a:
            st.markdown(
                render_html_grid(gt, agent_positions, width, height, shadow_filter=shadow_a),
                unsafe_allow_html=True,
            )
        else:
            st.info("No event for Agent A this turn.")
    with col_pb:
        st.subheader("Agent B Perspective")
        if event_b:
            st.markdown(
                render_html_grid(gt, agent_positions, width, height, shadow_filter=shadow_b),
                unsafe_allow_html=True,
            )
        else:
            st.info("No event for Agent B this turn.")

    # Legend — styled chips using the same colours as the grid cells
    _chip = (
        "display:inline-block;padding:2px 8px;border-radius:4px;"
        "font-family:monospace;font-size:13px;font-weight:bold;"
        "margin:2px 4px;color:#ffffff;"
    )
    st.markdown(
        f"""
        <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 0;">
          <span style="{_chip}background:#555555;">·</span><span style="font-size:12px;margin-right:6px;">empty</span>
          <span style="{_chip}background:#888888;">█</span><span style="font-size:12px;margin-right:6px;">wall</span>
          <span style="{_chip}background:#f0c040;">K</span><span style="font-size:12px;margin-right:6px;">key</span>
          <span style="{_chip}background:#e05050;">X</span><span style="font-size:12px;margin-right:6px;">exit (locked)</span>
          <span style="{_chip}background:#50c878;">O</span><span style="font-size:12px;margin-right:6px;">exit (open)</span>
          <span style="{_chip}background:#00bcd4;">A</span><span style="font-size:12px;margin-right:6px;">agent_a</span>
          <span style="{_chip}background:#5c6bc0;">B</span><span style="font-size:12px;margin-right:6px;">agent_b</span>
          <span style="{_chip}background:#ce93d8;">✦</span><span style="font-size:12px;margin-right:6px;">both agents</span>
          <span style="{_chip}background:#333333;">?</span><span style="font-size:12px;margin-right:6px;">fog of war</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Side-by-side turn inspector — both agents always visible
    # ------------------------------------------------------------------
    st.markdown("---")
    st.subheader(f"Turn Inspector — Turn {current_turn}")

    col_insp_a, col_insp_b = st.columns(2)
    _render_agent_inspector(event_a, "Agent A", col_insp_a)
    _render_agent_inspector(event_b, "Agent B", col_insp_b)


def _render_agent_inspector(event: dict | None, label: str, col) -> None:
    """Render Input / Output / Result sections for one agent inside *col*."""
    import streamlit as st

    with col:
        st.markdown(f"### {label}")

        if event is None:
            st.info("No event this turn.")
            return

        ctx    = event.get("state_context", {})
        ai     = ctx.get("agent_input", {})
        shadow = ctx.get("shadow_state", {})

        # ── Input ──
        st.markdown("**── Input ──**")
        loc = ai.get("last_known_location")
        if loc:
            loc_str = (
                f"({loc['position'][0]}, {loc['position'][1]}) "
                f"confirmed on turn {loc['turn_number']}"
            )
        else:
            loc_str = "(unknown)"
        st.markdown(f"Last known location: {loc_str}")
        st.markdown(f"Shadow map: {len(shadow)} cells observed")

        inbox = ai.get("message_inbox") or []
        st.markdown(f"Inbox: {'; '.join(inbox) if inbox else '(none)'}")

        mistake = ai.get("last_mistake")
        if mistake:
            st.markdown(
                f"Last mistake: `{mistake['tool_name']}` on turn "
                f"{mistake['turn_number']} — {mistake['reason']}"
            )
        else:
            st.markdown("Last mistake: (none)")

        calls = ai.get("recent_calls") or []
        if calls:
            call_parts = [
                f"T{c['turn_number']}: {c['tool_name']}"
                f"({', '.join(f'{k}={v!r}' for k, v in c.get('arguments', {}).items())})"
                for c in calls
            ]
            st.markdown(f"Recent calls: {', '.join(call_parts)}")
        else:
            st.markdown("Recent calls: (none)")

        # ── Output ──
        st.markdown("**── Output ──**")
        reasoning = ctx.get("agent_beliefs", {}).get("reasoning", "")
        st.markdown(f"*{reasoning}*" if reasoning else "*(no reasoning)*")

        tool_name = event["action"]["tool_name"]
        args = event["action"].get("arguments", {})
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if args else ""
        st.markdown(f"Action: `{tool_name}({args_str})`")

        # ── Result ── (always visible, no expander)
        st.markdown("**── Result ──**")
        result = event.get("execution_result", {})
        status = result.get("status", "")
        if status == "failure":
            error_msg = result.get("error_message") or ""
            if error_msg:
                st.error(f"Error: {error_msg}")
            deltas = result.get("deltas") or []
            if deltas:
                st.markdown("State Desync Diff:")
                for delta in deltas:
                    st.code(
                        f"EXPECTED: {delta['property_key']} = {delta['expected_value']!r}\n"
                        f"ACTUAL:   {delta['property_key']} = {delta['actual_value']!r}\n"
                        f"Source:   {delta['discrepancy_source']}",
                        language="diff",
                    )
            else:
                st.markdown("*(no state desync deltas)*")
        else:
            st.success("Success")


# ---------------------------------------------------------------------------
# Task 5 — Run Performance
# ---------------------------------------------------------------------------

def _render_run_performance(
    log_files: list[Path],
    compute_run_summary,
    compute_agent_efficiency,
    compute_delusion_timeline,
    compute_map_coverage,
    pd,
) -> None:
    import streamlit as st

    st.title("Run Performance")

    if not log_files:
        st.warning("No run_*.json files found in `saved_logs/`. Run a simulation first.")
        return

    # Log selection at top of page
    log_names = [p.name for p in log_files]
    selected_name = st.selectbox("Log file", log_names, key="perf_log")
    selected_path = next(p for p in log_files if p.name == selected_name)
    events = json.loads(selected_path.read_text(encoding="utf-8"))

    st.markdown("---")

    # A — Outcome summary
    summary = compute_run_summary(events)
    ec = summary["end_condition"]
    ec_color = "green" if ec == "SUCCESS" else "red" if ec == "TURN_LIMIT" else "orange"

    st.subheader("A. Run Outcome & Duration")
    st.caption("How the run ended, how many turns it lasted, and how far each agent was from the exit and key at the final turn.")
    c1, c2 = st.columns(2)
    c1.metric("End State", ec)
    c2.metric("Total Turns", summary["total_turns"])

    if ec != "SUCCESS":
        cols = st.columns(4)
        if summary["exit_pos"]:
            cols[0].metric("Exit Cell", str(summary["exit_pos"]))
        if summary["dist_a_to_exit"] is not None:
            cols[1].metric("Agent A → Exit", summary["dist_a_to_exit"])
        if summary["dist_b_to_exit"] is not None:
            cols[2].metric("Agent B → Exit", summary["dist_b_to_exit"])
        if summary["key_pos"]:
            cols[3].metric("Key Position", str(summary["key_pos"]))

    st.markdown("---")

    # B — Agent Efficiency
    st.subheader("B. Agent Efficiency")
    st.caption("Per-agent breakdown of which tools were called, how many failed, and how much each agent communicated via send_message.")
    efficiency = compute_agent_efficiency(events)
    for agent_id, data in sorted(efficiency.items()):
        st.markdown(f"**{agent_id}**")
        rows = []
        for tool, count in sorted(data["tool_counts"].items()):
            rows.append({"Tool": tool, "Count": count})
        df = pd.DataFrame(rows)
        df.loc[len(df)] = {"Tool": "— Total actions", "Count": data["total_actions"]}
        df.loc[len(df)] = {"Tool": "— Failures", "Count": data["failure_count"]}
        df.loc[len(df)] = {"Tool": "— Error rate", "Count": f"{data['error_rate']:.1f}%"}
        df.loc[len(df)] = {"Tool": "— Chatter (send_message)", "Count": data["chatter"]}
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # C — Delusion Timeline
    st.subheader("C. Delusion Timeline")
    st.caption("Every turn where the agent's expected state differed from ground truth, showing what was wrong, the source of the error, and how many turns until it was corrected.")
    timeline = compute_delusion_timeline(events)
    if timeline:
        df_t = pd.DataFrame(timeline)
        df_t["corrected_in"] = df_t["corrected_in"].apply(
            lambda v: "N/A" if v is None else ("never" if v == "never" else f"{v} turns")
        )
        st.dataframe(df_t, use_container_width=True, hide_index=True)
    else:
        st.info("No state desyncs recorded.")

    st.markdown("---")

    # D — Map Coverage
    st.subheader("D. Map Coverage")
    st.caption("Union of cells observed by either agent across the entire run, expressed as a percentage of the 64-cell grid.")
    coverage = compute_map_coverage(events)
    c1, c2, c3 = st.columns(3)
    c1.metric("Cells Observed (union)", coverage["observed"])
    c2.metric("Total Cells", coverage["total"])
    c3.metric("Coverage", f"{coverage['pct']:.1f}%")


# ---------------------------------------------------------------------------
# Task 6 — Global Insights
# ---------------------------------------------------------------------------

def _render_global_insights(
    log_dir: Path,
    compute_global_outcomes,
    compute_top_failure_drivers,
    compute_stubborn_failures,
    compute_tool_reliability,
    compute_avg_exploration_density,
    pd,
    go,
) -> None:
    import streamlit as st

    st.title("Global Insights")

    log_files = list_log_files(log_dir)
    if not log_files:
        st.warning(f"No run_*.json files found in `{log_dir}/`.")
        return

    runs = []
    for p in log_files:
        try:
            runs.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass

    if not runs:
        st.warning("No valid log files could be loaded.")
        return

    # A — Global Outcomes
    st.subheader("A. Global Run Outcomes")
    st.caption("Aggregate success and failure rates across all recorded runs, including average turns to completion and failure type distribution.")
    outcomes = compute_global_outcomes(runs)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Runs", outcomes["total_runs"])
    c2.metric("Successes", outcomes["success_count"])
    c3.metric("Success Rate", f"{outcomes['success_rate']:.1f}%")
    avg = outcomes["avg_completion_turns"]
    c4.metric("Avg Turns (success)", f"{avg:.1f}" if avg is not None else "N/A")
    c5.metric("Turn-limit Failures", outcomes["turn_limit_count"])

    st.markdown("---")

    # B — Top Failure Drivers
    st.subheader("B. Top Failure Drivers")
    st.caption("The five most frequent causes of action failures across all runs, ranked by how often they appear in the state desync diffs or error messages.")
    drivers = compute_top_failure_drivers(runs)
    if drivers:
        df_d = pd.DataFrame(drivers, columns=["Reason", "Count"])
        df_d.insert(0, "Rank", range(1, len(df_d) + 1))
        st.table(df_d)
    else:
        st.info("No failures recorded.")

    st.markdown("---")

    # C — Stubbornness Index
    st.subheader("C. Stubbornness Index")
    st.caption("How often an agent immediately repeated the exact same failing action back-to-back, expressed as a percentage of all failures.")
    stubbornness = compute_stubborn_failures(runs)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Failures", stubbornness["total_failures"])
    c2.metric("Stubborn Repeats", stubbornness["stubborn_count"])
    c3.metric("Stubbornness Rate", f"{stubbornness['pct']:.1f}%")

    st.markdown("---")

    # D — Tool Reliability (Plotly horizontal bar)
    st.subheader("D. Tool Reliability")
    st.caption("Failure rate per tool across all runs — how often each tool call returned an error rather than succeeding.")
    reliability = compute_tool_reliability(runs)
    tools = sorted(reliability.keys())
    failure_rates = [reliability[t]["failure_rate"] for t in tools]
    fig = go.Figure(go.Bar(
        x=failure_rates,
        y=tools,
        orientation="h",
        marker_color=[
            "#e05050" if r > 20 else "#5c6bc0" for r in failure_rates
        ],
        text=[f"{r:.1f}%" for r in failure_rates],
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_title="Failure Rate (%)",
        yaxis_title="Tool",
        height=max(300, len(tools) * 50),
        margin=dict(l=20, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Color scheme: "
        "🔴 Red — failure rate > 20%  |  🔵 Blue — failure rate ≤ 20%"
    )

    st.markdown("---")

    # E — Exploration Density
    st.subheader("E. Average Exploration Density")
    st.caption("Percentage of the 64-cell grid observed by either agent in each run, and the mean across all runs.")
    density = compute_avg_exploration_density(runs)
    st.metric("Average Coverage", f"{density['avg_pct']:.1f}%")

    per_run_data = [
        {"Run": f"Run {i + 1} ({log_files[i].name})", "Coverage (%)": round(pct, 1)}
        for i, pct in enumerate(density["per_run"])
    ]

    fig2 = go.Figure(go.Bar(
        x=[r["Run"] for r in per_run_data],
        y=[r["Coverage (%)"] for r in per_run_data],
        marker_color="#50c878",
        text=[f"{r['Coverage (%)']:.1f}%" for r in per_run_data],
        textposition="outside",
    ))
    fig2.update_layout(
        yaxis_title="Coverage (%)",
        yaxis_range=[0, 105],
        height=300,
        margin=dict(l=20, r=20, t=20, b=80),
    )
    st.plotly_chart(fig2, use_container_width=True)


if __name__ == "__main__":
    main()
