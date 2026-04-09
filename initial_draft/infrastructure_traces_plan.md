# Infrastructure & Observability Tracing Strategy

## 1. Objective
To satisfy the requirement of capturing the "end-to-end picture" (LLM inputs/outputs, latency, token usage) without cluttering the semantic game logic logs.

## 2. Tool Selection: Langfuse
We will use Langfuse (via the `langfuse-python` SDK) because it is explicitly designed for LLM observability, has native integrations with standard LLM frameworks, and provides clean UI exports out-of-the-box.

## 3. What Will Be Recorded
Every call to the LLM agent will be wrapped in a Langfuse trace. This will automatically capture:
* **Trace ID:** Links the LLM call to a specific game turn.
* **Raw Input (Prompt):** The exact system instructions and state representation sent to the LLM.
* **Raw Output (Completion):** The raw JSON string returned by the LLM (containing reasoning and tool calls).
* **Latency:** Execution time in milliseconds.
* **Token Usage:** Prompt tokens, completion tokens, and total cost.
* **Model Info:** e.g., `gpt-4o-mini` or `claude-3-5-sonnet`.

## 4. Recording Mechanism
We will implement a standard decorator or wrapper function around the core LLM execution block in the game loop. 

**Pseudocode Example:**
```python
from langfuse.decorators import observe

@observe(name="agent_turn_execution")
def get_agent_decision(agent_state, system_prompt):
    # Langfuse automatically captures the inputs, outputs, and latency of this block
    response = llm_client.chat.completions.create(...)
    return response