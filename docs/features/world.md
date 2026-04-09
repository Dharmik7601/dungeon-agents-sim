# World

## What It Does
Owns the authoritative ground truth of the dungeon at all times. Provides procedural map generation with a BFS solvability guarantee, and exposes `WorldState` as the single source of truth that the game loop and tool dispatcher read from and write to. Agents never receive a reference to this object directly.

## Implementation

## Key Files

## Testing
- **Unit** — `CellType` enum values; `WorldState` field defaults; BFS finds paths on known grids; BFS returns false on blocked grids; generator respects obstacle density cap (≤15%); generator always places key and exit on non-wall cells
- **Integration** — `generate_valid_world()` never returns an unsolvable map across 100 random seeds; returned map dimensions are ≥ 8×8
- **Edge cases** — grid fully walled off triggers silent regeneration; agent start positions never overlap key or exit; maximum retries before raising a generation error
