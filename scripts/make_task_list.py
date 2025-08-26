#!/usr/bin/env python3
"""Generate a frozen task list for reproducible evaluation."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.eval.harness import EvalHarness


def main():
    parser = argparse.ArgumentParser(description="Generate frozen task list for evaluation")
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Dataset split to use"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of tasks to include"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2025,
        help="Random seed for task selection"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output path for task list JSONL"
    )
    parser.add_argument(
        "--mode",
        choices=["stub", "swe"],
        default="stub",
        help="Mode for task generation (stub for testing, swe for real)"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use offline cached data only"
    )
    
    args = parser.parse_args()
    
    # Initialize harness to load tasks
    harness = EvalHarness(
        mode=args.mode,
        seed=args.seed,
        split=args.split,
        limit=args.limit,
        offline=args.offline
    )
    
    # Load tasks
    tasks = harness.load_tasks(n_episodes=args.limit)
    
    # For stub mode with repetitions, we need to handle suffixed task IDs
    # Extract base task IDs (remove __rep_N suffixes)
    task_ids = []
    seen_base_ids = set()
    
    for task in tasks:
        task_id = task.task_id
        # Remove repetition suffix if present
        base_id = task_id.split("__rep_")[0] if "__rep_" in task_id else task_id
        
        # For stub mode, ensure we get unique base IDs up to limit
        if args.mode == "stub":
            if base_id not in seen_base_ids:
                task_ids.append({"task_id": base_id})
                seen_base_ids.add(base_id)
                if args.limit and len(task_ids) >= args.limit:
                    break
        else:
            # For SWE mode, use exact task IDs
            task_ids.append({"task_id": task_id})
    
    # If we need more tasks in stub mode, cycle through base tasks
    if args.mode == "stub" and args.limit and len(task_ids) < args.limit:
        base_tasks = list(seen_base_ids)
        rng = random.Random(args.seed)
        rng.shuffle(base_tasks)
        
        # Add repetitions with explicit suffixes
        rep = 1
        while len(task_ids) < args.limit:
            for base_id in base_tasks:
                if len(task_ids) >= args.limit:
                    break
                task_ids.append({"task_id": f"{base_id}__rep_{rep}"})
            rep += 1
    
    # Write task list
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for task_entry in task_ids:
            json.dump(task_entry, f)
            f.write("\n")
    
    # Print summary
    print(f"Task list generated:")
    print(f"  Mode: {args.mode}")
    print(f"  Split: {args.split}")
    print(f"  Seed: {args.seed}")
    print(f"  Tasks: {len(task_ids)}")
    print(f"  Output: {output_path}")
    
    if args.mode == "stub":
        unique_base = len(seen_base_ids)
        print(f"  Unique base tasks: {unique_base}")
        if len(task_ids) > unique_base:
            print(f"  Repetitions included: {len(task_ids) - unique_base}")
    
    # Show first few task IDs
    print("\nFirst 5 task IDs:")
    for i, entry in enumerate(task_ids[:5]):
        print(f"  {i+1}. {entry['task_id']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())