# Project Plan: Dungeon Agents Simulation

## 1. Project Overview & Primary Aim
This project is a multi-agent simulation where two AI agents explore a grid-based dungeon. The primary aim of this project is **not** to build a sophisticated video game or to prompt-engineer the agents to play perfectly. 

Instead, the core objective is to generate deep, structured observability traces of the agents' decision-making processes. The system is designed to artificially induce "hard bugs" (where agents make reasonable decisions based on stale or out-of-sync information) and capture the exact delta between an agent's belief state and the ground truth reality.

*Note: For the detailed schema on how these traces are structured and how they feed into the diagnostic CLI tool, please refer to the `agent_trace.md`, `infrastructure_traces_plan.md`, and `cli_diagnostic_tool_spec.md` documents.*

## 2. Game Mechanics & Rules
The simulation adheres strictly to the following environmental constraints:
* **The World:** A 2D grid dungeon of at least 8x8 in size. It contains random obstacles (interior walls), a locked exit door, and a key.
* **Starting Conditions:** Both agents spawn in random, valid locations.
* **The Shared Objective:** Both agents must reach the exit. One agent must possess and use the key to unlock the door.
* **Fog of War:** Agents do not have a global view of the map; they can only observe their current cell and adjacent cells. 
* **Delayed Communication:** Messages sent between agents are not delivered instantly; they arrive on the following turn to intentionally cause state desynchronization.

## 3. Agent Definition & Toolset
Each agent is powered by an LLM and interacts with the simulation strictly through tool calls. Agents may only execute one tool call per turn.

**Available Tools:**
* `move(direction)`: Moves the agent one cell (North, South, East, West).
* `look()`: Updates the agent's internal map with current and adjacent cell contents.
* `pick_up(item)`: Grabs a specified item in the agent's current cell.
* `check_coordinates()`: Returns the agent's current [x, y] position.
* `check_inventory()`: Returns a list of items the agent is holding.
* `use_item(item, target)`: Applies an item to a target (e.g., using the key on the door).
* `send_message(agent, message)`: Sends text to the partner agent (delivered next turn).

## 4. Implementation Architecture
* **Language:** Python (Preferred by the assignment requirements).
* **LLM Engine:** Gemma 4 via the Google Generative AI Python SDK.
* **Orchestration Framework:** Custom "Vanilla" Python Game Loop. We are intentionally avoiding heavy frameworks (like LangGraph or LangChain)  to maintain absolute programmatic control over the turn order, message queues, and JSON state extraction.
* **Prompting Strategy:** External XML Files. The system prompt will not be hardcoded in the Python logic. It will live in a separate `prompt.md` file. The Python engine will read this file and use string replacement (e.g., `<current_state>{{STATE}}</current_state>`) to inject the dynamic shadow state into the prompt before each API call.

## 5. World Generation & Validation
To ensure the game is playable while maintaining variability:
* **Generation:** The 8x8 board will be procedurally generated at the start of each run. 
* **Density:** Obstacles (interior walls) will be capped at 10-15% of the board to prevent overly complex mazes.
* **Validation (BFS):** Before starting the loop, a programmatic Breadth-First Search (BFS) will verify that traversable paths exist from Agent A to the Key, Agent B to the Key, and the Key to the Exit. If a map is impossible, it is regenerated silently.

## 6. Game Loop & End-Game Conditions
The simulation runs sequentially (Agent A acts, then Agent B acts). The game terminates under any of the following conditions:
* **Success:** Both agents are at the exit and the door is unlocked.
* **Turn Limit:** The simulation reaches a hard cap of 50 turns. 
* **Action Deadlock:** An agent becomes "stuck," defined as making 5 consecutive invalid tool calls (e.g., walking into a wall repeatedly).
* **Parsing Deadlock:** The LLM returns malformed JSON that cannot be parsed 3 times in a single turn.

## 7. Execution & Output Presentation
* **How it is Played:** The simulation is entirely autonomous. The user does not "play" the game interactively. A human operator triggers a run via the command line (e.g., `python run_simulation.py`).
* **Runtime Presentation:** During execution, the terminal will print lightweight, high-level status updates so the operator knows the simulation is running (e.g., `[Run 01] Turn 12: Agent A moved North. Agent B sent a message.`). 
* **Final Output:** The true "output" of the simulation is the generation of two separate files upon completion:
    1.  The standard infrastructure traces (latency, tokens, raw I/O) exported via Langfuse or OpenTelemetry[cite: 38].
    2.  The highly structured, custom JSON diagnostic log (`run_data.json`) containing the state deltas[cite: 41, 62].
* **Review Process:** The operator then uses the standalone CLI Diagnostic Viewer tool to replay, visualize, and diagnose the generated `run_data.json` file.