# Game Loop

## What It Does
Orchestrates the entire simulation run: sequences turns (Agent A → Agent B), delivers delayed messages, drives the per-turn LLM → tool → trace pipeline, checks all end conditions after each agent acts, and prints lightweight terminal status so the operator can see progress. The loop holds references to `WorldState`, both `AgentState` objects, `SemanticLogger`, and `LLMClient` but does not implement any of their logic directly.

## Implementation

## Key Files

## Testing
- **Unit** — message delivery: outbox contents move to partner inbox exactly one turn later; turn counter increments correctly; each end condition triggers at the right moment (success, turn limit, action deadlock, parse deadlock)
- **Integration** — a scripted run (tool calls mocked to return fixed results) produces the correct sequence of terminal status lines and passes the correct state to `SemanticLogger` on each turn
- **Edge cases** — both agents deadlock simultaneously; success condition fires mid-turn (Agent A unlocks door, Agent B is already at exit); turn limit reached on turn 50 exactly
