# Cross-Run Aggregate Analysis Plan (`cross_run_analysis.md`)

## 1. Objective
To parse an entire directory of logs (e.g., `saved_logs/`) and output systemic behavioral trends. This proves to the reviewers that the infrastructure can diagnose prompt and orchestration issues at scale.

## 2. Calculated Metrics

### A. Global Run Outcomes
* **Overall Success Rate:** % of runs that achieved the objective.
* **Average Completion Turns:** Only calculated for successful runs.
* **Failure Distribution:** % of failures caused by Timeouts vs. % caused by Deadlocks.

### B. Top Failure Drivers (The "Delusion + Error" Metric)
This captures exactly *why* agents fail, combining state desyncs and logic errors.
* **Logic Flow:**
  1. Find an event where `status == "failure"`.
  2. If `deltas` array is NOT empty: Record the `property_key` (e.g., `partner_position`, `cell_status`).
  3. If `deltas` array IS empty: Record the `error_message` string (e.g., "Cannot move east: wall").
* **Output:** A sorted frequency chart of the top 5 reasons actions fail across all runs.

### C. The Stubbornness Index (Action Loops)
* **Logic:** Detect instances where `execution_result.status == "failure"` on Turn N, and on Turn N+1, the agent attempts the exact same `action` despite the `last_mistake` context.
* **Output:** Percentage of total failures that are immediate, stubborn repeats.

### D. Tool Reliability
* **Logic:** Count `Total Executions` and `Total Failures` grouped by `tool_name`.
* **Output:** A failure rate percentage for each specific tool to isolate mechanical prompt issues.

### E. Average Exploration Density
* **Logic:** Average the "Map Coverage" statistic (calculated in the Single-Run logic) across all parsed runs. 
* **Insight:** Shows if the agents generally explore broadly or get stuck in small areas before timing out.