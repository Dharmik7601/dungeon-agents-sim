# Implementation Plan: Streamlit Observability Dashboard

This document provides a comprehensive technical specification for the `dungeon-agents-sim` Streamlit dashboard. The goal is to consolidate all diagnostic and analytical features currently provided by the CLI scripts into a unified, high-legibility web interface.

## 1. Project Requirements & Dependencies
The following libraries must be added to the project environment (e.g., `requirements.txt`):
* **`streamlit`**: Main web framework for building the interactive dashboard.
* **`pandas`**: For managing and displaying structured data tables (efficiency metrics, timelines, failure drivers).
* **`plotly`**: For interactive data visualizations (Tool Reliability bar charts, Exploration Density charts).

## 2. File Architecture
* **Target File**: `src/cli/streamlit_app.py`
* **Core Dependencies**: The app must import and utilize existing logic from the following modules to ensure a single source of truth:
    * `src.cli.board_renderer`: For board snapshots, cell symbols, and state rendering logic.
    * `src.cli.single_run_analysis`: For individual run metrics, efficiency stats, and delusion timelines.
    * `src.cli.cross_run_analysis`: For global success rates, stubbornness indices, and aggregate failure drivers.
    * `src.cli.diagnostic_viewer`: For Input/Output formatting logic (e.g., `_fmt_input_lines`, `_fmt_location`).

## 3. Application Structure & Features

### A. Sidebar: Navigation & Configuration
* **Log Selection**: A `st.selectbox` that scans the `saved_logs/` directory and lists available `run_*.json` files. It must filter out active `run_wip_*.json` files.
* **Mode Selector**: A navigation menu (radio buttons or tabs) to switch between:
    1.  **Interactive Replay**: Visual turn-by-turn debugger.
    2.  **Run Performance**: Deep-dive metrics for the selected log.
    3.  **Global Insights**: Aggregate trends across all recorded logs.

### B. Interactive Replay (The Viewer)
This component visualizes the divergence between "Ground Truth" reality and "Shadow State" beliefs.
* **Turn Controller**: A `st.slider` to scrub through turns (0 to total turns).
* **Perspective Toggle**: A radio button to switch the "Shadow State" view between `agent_a` and `agent_b`.
* **Side-by-Side Grid Visualization**:
    * Render two 8×8 grids using HTML/CSS inside `st.markdown(unsafe_allow_html=True)`.
    * **Reality Pane**: Displays authoritative world state from `state_context.ground_truth`.
    * **Agent Perspective Pane**: Displays cells present in the selected agent's `shadow_state`. Cells not yet observed must be rendered as "Fog of War" (dark grey squares).
* **Detailed Turn Inspector**:
    * **Input**: Show Last Known Location (position + turn), Shadow Size, Inbox messages, Last Mistake, and Recent Calls.
    * **Output**: Display the LLM reasoning quote (italicized) and the exact tool/arguments used.
    * **Result**: For failures, show a red `st.error` panel with the Error Message and the State Desync Diff (Expected vs. Actual).

### C. Run Performance (Single-Run Analysis)
Integrate every metric from the `single_run_analysis` module:
* **Outcome Summary**: Metric cards for **End State** (SUCCESS, TURN_LIMIT, OTHER) and **Total Turns**.
* **Spatial Status**: If not a success, display the **Exit Cell** position and **Manhattan distances** from each agent to the exit/key.
* **Agent Efficiency**: Per-agent `st.dataframe` showing Tool Counts, Total Actions, Failure Count, Error Rate, and Chatter.
* **Delusion Timeline**: A detailed table tracking every state desync: Turn, Agent, Property, Expected, Actual, Source, and **Time-to-Correction** (turns until shadow map matched reality).
* **Map Coverage**: Metric for unique cells observed vs. total (64) and the coverage percentage.

### D. Global Insights (Cross-Run Analysis)
Aggregate data across all logs in `saved_logs/` using the `cross_run_analysis` logic:
* **Global Outcomes**: Display Total Runs, Successes (Count and %), Avg turns to success, and failure distribution (Turn-limit vs. Other).
* **Top Failure Drivers**: A ranked `st.table` of the top-5 property keys or error messages causing incidents.
* **Stubbornness Index**: A high-level metric showing the count and percentage of "Stubborn repeats" (repeating a failed action).
* **Tool Reliability**: A horizontal `plotly` bar chart showing the failure rate per tool across all runs.
* **Exploration Density**: A table or chart showing per-run coverage percentage and the overall average.

## 4. Technical Helper: HTML Grid Renderer
Implement a helper function to translate simulation states into styled HTML tables, replacing the terminal-specific `rich.Table`.

```python
def render_html_grid(grid_data, agent_positions, shadow_filter=None):
    """
    Generates a CSS-styled HTML table for the 8x8 dungeon.
    - grid_data: Dict of cell_status_x_y from the semantic log.
    - agent_positions: Dict containing current (x,y) for A and B.
    - shadow_filter: If provided, masks cells not in the agent's shadow map.
    """
    # Mapping logic:
    # Wall -> █ (white) | Key -> K (yellow) | Exit Locked -> X (red)
    # Exit Open -> O (green) | Empty -> · (dim) | Unknown -> (dark grey)
```