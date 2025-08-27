#!/usr/bin/env python3
"""Generate real task list from Hugging Face SWE-bench Lite dataset."""

import argparse
import json
import os
import random
from pathlib import Path

from datasets import load_dataset


def _load_swe_dataset(split: str):
    """Load SWE-bench Lite dataset with fallback."""
    # Try official namespace first
    try:
        print(f"Loading SWE-bench Lite {split} split from official namespace...")
        ds = load_dataset("SWE-bench/SWE-bench_Lite", split=split)
        print(f"Loaded from official namespace: {len(ds)} tasks")
        return ds, "SWE-bench/SWE-bench_Lite"
    except Exception as e:
        print(f"Official namespace failed: {e}")
        # Try legacy namespace
        try:
            print(f"Trying legacy namespace...")
            ds = load_dataset("princeton-nlp/SWE-bench_Lite", split=split)
            print(f"Loaded from legacy namespace: {len(ds)} tasks")
            return ds, "princeton-nlp/SWE-bench_Lite"
        except Exception as e2:
            print(f"Legacy namespace also failed: {e2}")
            raise RuntimeError(f"Could not load SWE-bench Lite {split} split from either namespace")


def main():
    parser = argparse.ArgumentParser(description="Generate real task list from SWE-bench Lite")
    parser.add_argument("--split", required=True, choices=["dev", "test"], help="Dataset split")
    parser.add_argument("--n", type=int, required=True, help="Number of tasks to sample")
    parser.add_argument("--seed", type=int, required=True, help="Random seed for deterministic sampling")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--use-test-as-dev", action="store_true", 
                        help="Use test split as dev (for SWE-bench Lite where dev only has 23)")
    
    args = parser.parse_args()
    
    # Handle the fact that SWE-bench Lite dev only has 23 tasks while test has 300
    # Per the MVP spec, we treat the 300-task split as our "dev" for evaluation
    split_to_load = args.split
    if args.use_test_as_dev and args.split == "dev":
        print("Note: Using test split as dev (SWE-bench Lite dev only has 23 tasks)")
        split_to_load = "test"
    
    # Load dataset
    ds, namespace_used = _load_swe_dataset(split_to_load)
    
    print(f"Total tasks in {split_to_load} split (used as {args.split}): {len(ds)}")
    
    if args.n > len(ds):
        raise ValueError(f"Requested {args.n} tasks but {args.split} split only has {len(ds)} tasks")
    
    # Deterministic sampling
    rng = random.Random(args.seed)
    all_task_ids = [row["instance_id"] for row in ds]
    
    # Sample without replacement
    sampled_ids = rng.sample(all_task_ids, args.n)
    
    # Verify uniqueness
    assert len(sampled_ids) == len(set(sampled_ids)), "Sampled IDs are not unique"
    
    # Verify all IDs exist in dataset
    dataset_ids = set(all_task_ids)
    for task_id in sampled_ids:
        assert task_id in dataset_ids, f"Task ID {task_id} not found in dataset"
    
    # Create output directory if needed
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to file - one object per line
    with open(output_path, "w") as f:
        # Write task IDs
        for task_id in sampled_ids:
            json.dump({"task_id": task_id}, f)
            f.write("\n")
        
        # Write metadata as final line
        metadata = {
            "__meta__": {
                "split": args.split,
                "split_source": split_to_load,  # Actual HF split used
                "dataset": namespace_used,
                "seed": args.seed,
                "n": len(sampled_ids),
                "generated_by": "scripts/generate_real_task_list.py"
            }
        }
        if args.use_test_as_dev:
            metadata["__meta__"]["note"] = f"{args.n} tasks sampled from {split_to_load} split (dev only has 23 tasks)"
        json.dump(metadata, f)
        f.write("\n")
    
    print(f"\n✅ Generated task list with {len(sampled_ids)} unique tasks")
    print(f"   Namespace used: {namespace_used}")
    print(f"   Seed: {args.seed}")
    print(f"   Output: {args.out}")
    print(f"\nFirst 10 task IDs:")
    for i, task_id in enumerate(sampled_ids[:10]):
        print(f"  {i+1}. {task_id}")


if __name__ == "__main__":
    main()