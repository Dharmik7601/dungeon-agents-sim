# World

## What It Does
Owns the authoritative ground truth of the dungeon at all times. Provides procedural map generation with a BFS solvability guarantee, and exposes `WorldState` as the single source of truth that the game loop and tool dispatcher read from and write to. Agents never receive a reference to this object directly.

## Implementation
Two modules:

**`src/world/state.py`** — defines `CellType` (Enum) and `WorldState` (dataclass). `WorldState` holds the 2D grid, entity positions, lock state, and turn counter. Its `in_bounds(x, y)` helper is used throughout the tool dispatcher and loop. This object is never passed to agents.

**`src/world/generator.py`** — three functions:
- `generate_map(width, height, seed)` places walls (randomly sampled up to 15% density), then picks four non-overlapping empty cells for key, exit, agent_a, and agent_b.
- `bfs_path_exists(grid, start, goal)` runs standard BFS treating only `WALL` as impassable. `EXIT_LOCKED` is treated as passable so solvability can be validated before the game begins.
- `generate_valid_world(seed)` calls `generate_map` and runs three BFS checks (agent_a→key, agent_b→key, key→exit). Retries silently up to 100 times; raises `RuntimeError` on exhaustion.

## Key Files
- `src/world/state.py`
  - `CellType` (Enum) — `EMPTY`, `WALL`, `KEY`, `EXIT_LOCKED`, `EXIT_UNLOCKED`
  - `WorldState` (dataclass) — `grid`, `key_pos`, `exit_pos`, `agent_positions`, `exit_locked`, `turn_number`
  - `WorldState.in_bounds(x, y) -> bool` — bounds check helper
- `src/world/generator.py`
  - `bfs_path_exists(grid, start, goal) -> bool` — BFS reachability; WALL impassable
  - `generate_map(width, height, seed) -> WorldState` — raw generation, no validation
  - `generate_valid_world(seed=None) -> WorldState` — validated public entry point

## Testing
- **Unit** — `CellType` has all 5 members; `WorldState` defaults (`exit_locked=True`, `turn_number=0`); `in_bounds` for corners and out-of-bounds; BFS on open grid (True), walled grid (False), start==goal (True), through EXIT_LOCKED (True); `generate_map` wall density ≤15% across 20 seeds; entity positions on non-wall cells; no two entities share a cell; all positions in bounds
- **Integration** — `generate_valid_world()` returns solvable maps across 50 random seeds; grid always 8×8
- **Edge cases** — `generate_valid_world` raises `RuntimeError` when `generate_map` is patched to always return an unsolvable map
