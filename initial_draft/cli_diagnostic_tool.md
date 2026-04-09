
# Diagnostic CLI Tool Specification (The Legibility Layer)

## 1. Objective
To build a lightweight, highly intentional command-line interface that helps a human answer: "What happened?", "Why did it happen?", and "What should change next?" by parsing the custom semantic JSON logs.

## 2. Tech Stack
* **Language:** Python
* **Core Library:** `rich` (for advanced terminal formatting, colors, panels, and diffs).
* **CLI Parser:** `argparse`

## 3. Tool Interface & Arguments
The tool will be executed from the terminal to replay a specific game run.

**Command Structure:**
`python diagnostic_viewer.py --log-file data/run_42.json [OPTIONS]`

**Available Arguments:**
* `--log-file` (Required): Path to the custom JSON trace file.
* `--filter` (Optional): `all` (default) or `failures_only`. Allows the reviewer to skip successful turns and jump straight to bugs.
* `--agent` (Optional): Filter the timeline to only show actions by `Agent_A` or `Agent_B`.

## 4. Visual Layout & Data Mapping
The CLI will iterate through the JSON array sequentially, rendering a specific visual block for each event based on its `execution_result.status`.

### Scenario A: Successful Execution
Successful turns are rendered as muted, single-line log entries to save space while maintaining the timeline.
* **Style:** Dim gray text, no borders.
* **Format:** `[Turn X] {agent_id} successfully executed {tool_name} with args: {arguments}`
* **Example:** `[Turn 12] Agent_A successfully executed move with args: {'direction': 'north'}`

### Scenario B: Failed Execution (The Incident Block)
Failures are expanded into highly visible, color-coded panels that extract exactly why the failure occurred using the `deltas` array.

* **Style:** Bright Red or Orange bordered Panel using `rich.panel`.
* **Header:** `[!] DIAGNOSTIC EVENT: {agent_id} | Turn {turn_number}`
* **Section 1: What Happened (Action Attempted)**
    * Reads from: `action.tool_name` and `action.arguments`
    * Output: `Attempted to use tool 'use_item' with arguments {'item': 'silver_key'}`
* **Section 2: Why It Happened (State Desync Diff)**
    * Reads from: `execution_result.deltas`
    * Format: A unified diff view highlighting the fractured reality.
    * Output Example:
        ```diff
        --- AGENT EXPECTED ---
        + {property_key}: {expected_value}
        --- GROUND TRUTH ---
        - {property_key}: {actual_value}
        (Source of discrepancy: {discrepancy_source})
        ```
* **Section 3: What Should Change Next (LLM Reasoning)**
    * Reads from: `state_context.agent_beliefs.reasoning`
    * Style: Italicized text inside a blockquote format.
    * Output: *"Agent Reasoning: Agent_B messaged me that they are waiting at the exit door. I have the silver key..."*

## 5. Workflow Example
1.  The simulation runs and outputs two things: background traces to Langfuse, and `run_42_semantic_log.json` locally.
2.  The user runs: `python diagnostic_viewer.py --log-file run_42_semantic_log.json --filter failures_only`
3.  The CLI immediately prints the Red Incident Panels.
4.  The developer reads Section 2 (The Diff) and sees that `partner_position` was mismatched. 
5.  The developer reads Section 3 (The Reasoning) and realizes the agent acted on a message that was 2 turns old.
6.  *Diagnosis Complete:* The developer now knows they need to update the system prompt to tell agents to verify coordinates before using the key, rather than relying solely on old messages.