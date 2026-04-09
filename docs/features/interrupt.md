# Ctrl+E Interrupt

## What It Does
Allows the user to stop the simulation mid-run by pressing Ctrl+E. All semantic log events up to that point are preserved in the crash-safe WIP file (which already writes after every action). The simulation exits cleanly with `EndCondition.INTERRUPTED`.

## Implementation

`EndCondition.INTERRUPTED` added to the enum. `GameLoop.__init__` accepts an optional `stop_event: threading.Event | None`. `GameLoop.run()` checks `stop_event.is_set()` at the top of each iteration and again after Agent A acts, returning `RunResult(INTERRUPTED, ...)` immediately if set. The logger is flushed on interrupt just like any other end condition — the WIP file already contains all events up to that point.

`run_simulation.py` creates the event, calls `_start_interrupt_listener(stop_event)` which spawns a daemon thread using `msvcrt.kbhit()` + `msvcrt.getch()` to poll for Ctrl+E (byte `0x05`). Falls back silently if `msvcrt` is unavailable (non-Windows) or stdin is not a TTY. A `(Ctrl+E to stop)` hint is printed at startup.

## Key Files
- `src/loop/game_loop.py`
  - `EndCondition.INTERRUPTED` — new enum value
  - `GameLoop.__init__(stop_event: threading.Event | None = None)` — stores event
  - `GameLoop.run()` — checks stop_event before each agent turn
- `src/loop/run_simulation.py`
  - `_start_interrupt_listener(stop_event)` — spawns daemon thread for Ctrl+E detection

## Testing
- **Unit** — `EndCondition.INTERRUPTED` exists; `GameLoop` accepts `stop_event`; event set before run returns `INTERRUPTED` without calling LLM; event set during Agent A's turn returns `INTERRUPTED` without Agent B acting; interrupted result flushes the logger
