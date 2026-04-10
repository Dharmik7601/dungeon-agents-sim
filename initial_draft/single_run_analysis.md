# Single-Run Analysis Plan (`single_run_analysis.md`)

## 1. Objective
To provide a highly detailed, statistical summary of a single simulation round (`run_*.json`) before or alongside the turn-by-turn replay. This gives the reviewer an immediate snapshot of agent efficiency and behavioral bottlenecks for that specific game.

## 2. Calculated Metrics

### A. Run Outcome & Duration
* **End State:** Did it end in Success, Timeout (50 turns), or Action Deadlock?
* **Total Turns Taken:** How fast was the resolution?
* **Final Grid Distance:** If failed, calculate the Manhattan distance between the key, the door, and the agents at the final turn.

### B. Agent Efficiency (Per Agent)
* **Action Breakdown:** Count of each tool used by Agent A vs. Agent B (e.g., A: 12 moves, 4 looks; B: 8 moves, 8 looks).
* **Individual Error Rate:** Percentage of actions that resulted in `status: "failure"`.
* **Chatter Volume:** Total `send_message` tools executed.

### C. The Delusion Timeline (Chronological)
Instead of aggregating, list the exact turns where reality fractured.
* **Format:** `Turn [X] - Agent [Y] - [Delta Key or Error Message]`
* **Time-to-Correction:** For each delusion, scan forward to see how many turns it took for the agent to update its `shadow_state` to match reality (if ever).

### D. Map Coverage
* Calculate the exact number of unique cells in the final `shadow_state` combined from both agents.
* Calculate `(Total Observed Cells / 64) * 100` to show the exploration density for this specific map.