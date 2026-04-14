# Streamlit Dashboard

## What It Does
A Streamlit web app (`src/cli/streamlit_app.py`) that consolidates the CLI diagnostic viewer, single-run analysis, and cross-run analysis into one interactive browser-based UI. Launch with `make streamlit`. Reads completed run logs from `saved_logs/`.

Three modes, selected via the sidebar:

1. **Interactive Replay** — turn-by-turn replay with ◀ Prev / turn input / Next ▶ navigation, three side-by-side HTML grids (Ground Truth, Agent A Perspective, Agent B Perspective with fog-of-war), and a permanent side-by-side turn inspector for both agents showing Input / Output / Result sections on every turn.
2. **Run Performance** — deep-dive single-run metrics: outcome + duration, agent efficiency table, delusion timeline, map coverage. Log file chosen at the top of the page.
3. **Global Insights** — cross-run aggregate trends: success rates, top failure drivers, stubbornness index, tool reliability Plotly bar chart, exploration density chart + average metric.

All metric computation is delegated to the existing `compute_*` functions in `single_run_analysis.py` and `cross_run_analysis.py`. Only the rendering layer is new.

## Implementation

### streamlit-dependencies
Added `streamlit>=1.40.0`, `pandas>=2.0.0`, `plotly>=5.0.0` to `requirements.txt`.
Added `make streamlit` target to `Makefile` (`streamlit run src/cli/streamlit_app.py`).

### html-grid-renderer
`render_html_grid(grid_data, agent_positions, width, height, shadow_filter=None) -> str` — pure function producing a CSS-styled HTML `<table>` string for the dungeon grid. No Streamlit dependency; used via `st.markdown(unsafe_allow_html=True)`.

- Cell symbol mapping: `·` empty, `█` wall, `K` key, `X` locked exit, `O` open exit
- Agent overlay: `A` cyan, `B` blue, `✦` magenta when both on same cell
- `shadow_filter`: if a `set` of `cell_status_X_Y` keys is provided, cells absent from it render as fog-of-war (`?`, dark grey)
- OOB coordinates are skipped safely

### app-scaffold
`list_log_files(directory: Path) -> list[Path]` — scans `saved_logs/` for `run_*.json`, excludes `run_wip_*.json`, returns sorted list.

Sidebar contains only the mode radio button. Log file selection appears at the top of the content area for Interactive Replay and Run Performance modes (not in the sidebar).

### interactive-replay
`_render_interactive_replay(log_files)`:
- Log selectbox at top of page
- Events grouped by `turn_number`; each turn holds one event per agent
- Navigation row: ◀ Prev button | turn text input | Next ▶ button | right spacer. Uses `st.columns(vertical_alignment="bottom")` for pixel-perfect alignment. Buttons use `use_container_width=True` to fill their columns and eliminate internal column gaps. `st.text_input` (not `st.number_input`) is used to avoid Streamlit's built-in `+`/`−` step buttons
- Turn input is fully dynamic: typing a valid number navigates to that turn; out-of-range values are clamped to the limits; non-numeric input is rejected and resets to the current turn; Prev/Next clicks update both the turn state and the text box display via explicit session state sync
- Three HTML grids: Ground Truth (no filter), Agent A Perspective (shadow from A's event), Agent B Perspective (shadow from B's event)
- HTML legend below grids with colour-matched chips for all cell types and agents
- Side-by-side turn inspector (`_render_agent_inspector`): both agents always visible, no toggle. Each column shows Input / Output / Result inline (no expanders) so all information is immediately visible

### run-performance
`_render_run_performance(log_files, ...)`:
- Log selectbox at top of page
- Section captions below each subheader explain what is displayed
- A. Run Outcome & Duration — metric cards for end state, total turns, distances
- B. Agent Efficiency — `st.dataframe` per agent with tool counts + summary rows
- C. Delusion Timeline — `st.dataframe` with corrected_in column formatted as turns / never / N/A
- D. Map Coverage — metric cards for observed cells, total cells, coverage %

### global-insights
`_render_global_insights(log_dir, ...)`:
- Section captions below each subheader explain what is displayed
- A. Global Run Outcomes — five metric cards
- B. Top Failure Drivers — `st.table` ranked list
- C. Stubbornness Index — three metric cards
- D. Tool Reliability — horizontal Plotly bar chart; bars coloured red (>20% failure) or blue (≤20%); colour scheme caption below chart
- E. Average Exploration Density — average metric card + Plotly bar chart per run (table removed)

## Key Files
- `src/cli/streamlit_app.py` — entire dashboard
  - `render_html_grid(grid_data, agent_positions, width, height, shadow_filter=None) -> str`
  - `list_log_files(directory: Path) -> list[Path]`
  - `main() -> None` — Streamlit entry point; sidebar mode selector; dispatches to render functions
  - `_render_interactive_replay(log_files: list[Path]) -> None`
  - `_render_agent_inspector(event: dict | None, label: str, col) -> None`
  - `_render_run_performance(log_files: list[Path], ...) -> None`
  - `_render_global_insights(log_dir: Path, ...) -> None`
- `requirements.txt` — added `streamlit>=1.40.0`, `pandas>=2.0.0`, `plotly>=5.0.0`
- `Makefile` — added `make streamlit` target

## Testing
- **Unit** — `render_html_grid`: symbol correctness (empty, wall, key, locked exit, open exit), agent-A overlay, agent-B overlay, both-agents overlay (✦), fog-of-war masking for unseen cells, known cells visible through shadow filter, no shadow filter shows all cells, returns valid HTML table tag
- **Unit** — `list_log_files`: returns sorted `run_*.json` paths, excludes `run_wip_*.json`, returns empty list when no matches, ignores non-JSON files
- **Dependency imports** — `streamlit`, `pandas`, `plotly` all importable after `pip install -r requirements.txt`
- **Edge cases** — fog-of-war with empty shadow_filter set renders all cells as `?`; cell present in shadow_filter renders with correct symbol through filter
