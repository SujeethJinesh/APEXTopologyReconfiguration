#!/usr/bin/env python3
"""Generate oracle smoke artifacts for validation.

Usage:
    # Generate oracle smoke results (applies gold patches)
    APEX_ALLOW_NETWORK=1 python scripts/generate_oracle_smoke.py --limit 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.eval.harness import EvalHarness


def main():
    parser = argparse.ArgumentParser(
        description="Generate oracle smoke artifacts for SWE-bench validation"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of tasks to validate",
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Dataset split to use",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="docs/M5/artifacts/oracle_smoke.jsonl",
        help="Output file for results",
    )

    args = parser.parse_args()

    # Check network permission
    if os.getenv("APEX_ALLOW_NETWORK") != "1":
        print("Error: Oracle smoke generation requires network access.")
        print("Please set APEX_ALLOW_NETWORK=1")
        sys.exit(1)

    print(f"Generating oracle smoke artifacts for {args.limit} tasks...")
    print(f"Split: {args.split}")
    print(f"Output: {args.out}")

    # Initialize harness with oracle mode
    harness = EvalHarness(
        mode="swe",
        split=args.split,
        limit=args.limit,
        offline=False,
        oracle_smoke=True,  # Apply gold patches
    )

    # Load tasks
    tasks = harness.load_tasks()
    print(f"Loaded {len(tasks)} tasks")

    # Run oracle validation
    results = []
    for i, task in enumerate(tasks):
        print(f"\nTask {i+1}/{len(tasks)}: {task.task_id}")
        print(f"  Repo: {task.metadata.get('repo', 'unknown')}")

        try:
            result = harness.run_episode(
                task=task,
                policy="static_star",
                budget=50000,  # Large budget for oracle mode
            )

            print(f"  Result: {'SUCCESS' if result.success else 'FAIL'}")
            print(f"  Tokens: {result.tokens_used}")

            results.append(result.to_dict())

        except Exception as e:
            print(f"  Error: {e}")
            results.append(
                {
                    "task_id": task.task_id,
                    "success": False,
                    "error": str(e),
                }
            )

    # Write results
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for result in results:
            json.dump(result, f)
            f.write("\n")

    # Summary
    successes = sum(1 for r in results if r.get("success", False))
    print(f"\n=== Oracle Smoke Summary ===")
    print(f"Tasks: {len(results)}")
    print(f"Successes: {successes}/{len(results)}")
    print(f"Output: {output_path}")

    # With oracle mode (gold patches), we expect high success rate
    if successes == len(results):
        print("✓ All tasks passed with gold patches")
    else:
        print(f"⚠ {len(results) - successes} tasks failed even with gold patches")

    # Clean up
    harness.cleanup()


if __name__ == "__main__":
    main()