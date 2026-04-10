"""Batch runner — executes the simulation N times sequentially."""

import argparse
import sys

from src.loop.run_simulation import run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the dungeon simulation N times in sequence.")
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of simulation runs (default: 10)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Starting run number for IDs (default: 1)",
    )
    args = parser.parse_args(argv)

    for i in range(args.start, args.start + args.runs):
        run_id = f"{i:02d}"
        print(f"\n{'='*60}")
        print(f"  Batch run {i}/{args.start + args.runs - 1}  (run_id={run_id})")
        print(f"{'='*60}\n")
        run(run_id=run_id)


if __name__ == "__main__":
    main()
