#!/usr/bin/env python3
"""Pick the best static policy per task from evaluation results."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: str) -> list:
    """Load JSONL file."""
    results = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def main():
    parser = argparse.ArgumentParser(description="Pick best static policy per task")
    parser.add_argument("--star", type=str, required=True, help="Path to static_star.jsonl")
    parser.add_argument("--chain", type=str, required=True, help="Path to static_chain.jsonl")
    parser.add_argument("--flat", type=str, required=True, help="Path to static_flat.jsonl")
    parser.add_argument("--out", type=str, required=True, help="Output path for static_best.jsonl")
    parser.add_argument("--verbose", action="store_true", help="Print detailed comparison")
    
    args = parser.parse_args()
    
    # Load all static results
    star_results = load_jsonl(args.star)
    chain_results = load_jsonl(args.chain)
    flat_results = load_jsonl(args.flat)
    
    # Group by task_id
    results_by_task = defaultdict(list)
    
    for result in star_results:
        # Skip metadata lines
        if "__meta__" in result:
            continue
        results_by_task[result["task_id"]].append(result)
    
    for result in chain_results:
        # Skip metadata lines
        if "__meta__" in result:
            continue
        results_by_task[result["task_id"]].append(result)
    
    for result in flat_results:
        # Skip metadata lines
        if "__meta__" in result:
            continue
        results_by_task[result["task_id"]].append(result)
    
    # Pick best for each task
    best_results = []
    comparison_stats = defaultdict(int)
    
    for task_id, candidates in results_by_task.items():
        # Ensure we only consider static policies
        static_candidates = [
            c for c in candidates 
            if c["policy"] in ["static_star", "static_chain", "static_flat"]
        ]
        
        if not static_candidates:
            print(f"Warning: No static results for task {task_id}")
            continue
        
        # Best = successful with lowest tokens, or if all fail, lowest tokens
        successful = [c for c in static_candidates if c["success"]]
        
        if successful:
            # Use correct field name: tokens_used_total
            best = min(successful, key=lambda x: x.get("tokens_used_total", x.get("tokens_used", 0)))
        else:
            # All failed, pick one with lowest tokens
            best = min(static_candidates, key=lambda x: x.get("tokens_used_total", x.get("tokens_used", 0)))
        
        # Create best result with clear labeling
        best_result = best.copy()
        best_result["original_policy"] = best["policy"]
        best_result["policy"] = "static_best"
        best_result["notes"] = f"Selected {best['policy']} as best static"
        
        best_results.append(best_result)
        comparison_stats[best["policy"]] += 1
        
        if args.verbose:
            print(f"Task {task_id}:")
            for c in static_candidates:
                status = "✓" if c["success"] else "✗"
                selected = "←BEST" if c == best else ""
                tokens = c.get('tokens_used_total', c.get('tokens_used', 0))
                print(f"  {c['policy']:12} {status} {tokens:5} tokens {selected}")
    
    # Sort by task_id for consistent output
    best_results.sort(key=lambda x: x["task_id"])
    
    # Write output
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        # Add metadata first
        metadata = {
            "__meta__": {
                "source": "derived",
                "generator": "pick_best_static.py",
                "inputs": {
                    "star": str(args.star),
                    "chain": str(args.chain),
                    "flat": str(args.flat)
                },
                "n_tasks": len(best_results)
            }
        }
        json.dump(metadata, f)
        f.write("\n")
        
        # Write results
        for result in best_results:
            json.dump(result, f)
            f.write("\n")
    
    # Print summary
    print(f"\nBest static selection summary:")
    print(f"Total tasks: {len(best_results)}")
    for policy, count in comparison_stats.items():
        pct = 100 * count / len(best_results) if best_results else 0
        print(f"  {policy}: {count} tasks ({pct:.1f}%)")
    
    success_count = sum(1 for r in best_results if r["success"])
    success_rate = 100 * success_count / len(best_results) if best_results else 0
    print(f"Success rate: {success_count}/{len(best_results)} ({success_rate:.1f}%)")
    
    avg_tokens = sum(r.get("tokens_used_total", r.get("tokens_used", 0)) for r in best_results) / len(best_results) if best_results else 0
    print(f"Avg tokens: {avg_tokens:.0f}")
    
    print(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()