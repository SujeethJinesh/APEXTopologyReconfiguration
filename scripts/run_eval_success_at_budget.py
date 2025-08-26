#!/usr/bin/env python3
"""Run evaluation episodes with Success@Budget metric."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.eval.harness import EvalHarness
from apex.eval.stubs.topology_switch import TopologySwitch


def main():
    parser = argparse.ArgumentParser(description="Run Success@Budget evaluation")
    parser.add_argument("--episodes", type=int, default=12, help="Number of episodes")
    parser.add_argument("--budget", type=int, default=10000, help="Token budget per episode")
    parser.add_argument(
        "--mode",
        choices=["stub", "swe"],
        default="stub",
        help="Evaluation mode (stub for CI, swe for SWE-bench Lite)"
    )
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="Dataset split for SWE mode"
    )
    parser.add_argument(
        "--policy",
        choices=["static_star", "static_chain", "static_flat", "bandit_v1", "apex_dynamic"],
        required=True,
        help="Policy to evaluate"
    )
    parser.add_argument("--out", type=str, required=True, help="Output JSONL file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cache-dir", type=str, help="Cache directory for SWE datasets")
    
    args = parser.parse_args()
    
    # Check network permission for SWE mode
    if args.mode == "swe" and not os.getenv("APEX_ALLOW_NETWORK"):
        print("Error: SWE mode requires network. Set APEX_ALLOW_NETWORK=1", file=sys.stderr)
        sys.exit(1)
    
    # Initialize harness
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    if args.mode == "swe":
        harness = EvalHarness(mode=args.mode, seed=args.seed, split=args.split, cache_dir=cache_dir)
    else:
        harness = EvalHarness(mode=args.mode, seed=args.seed)
    
    # Load tasks
    tasks = harness.load_tasks(n_episodes=args.episodes)
    
    # Setup switch and bandit for dynamic policy
    switch = None
    bandit = None
    if args.policy in ["bandit_v1", "apex_dynamic"]:
        switch = TopologySwitch(initial="star", seed=args.seed)
        bandit = BanditSwitchV1(d=8, seed=args.seed)
    
    # Run episodes and collect results
    results = []
    for task in tasks:
        result = harness.run_episode(
            task=task,
            policy=args.policy,
            budget=args.budget,
            switch=switch,
            bandit=bandit
        )
        results.append(result)
    
    # Write JSONL output
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for result in results:
            # Convert TaskResult to dict for JSON serialization
            result_dict = {
                "task_id": result.task_id,
                "policy": result.policy,
                "success": result.success,
                "tokens_used": result.tokens_used,
                "budget": result.budget,
                "over_budget": result.over_budget,
                "seed": result.seed,
            }
            
            # Add SWE-specific fields if present
            if hasattr(result, "metadata") and result.metadata:
                result_dict["budget_denied"] = result.metadata.get("budget_denied", 0)
                result_dict["topology_trace"] = result.metadata.get("topology_trace", [])
                result_dict["switches"] = result.metadata.get("switches", 0)
                result_dict["episode_ms"] = result.metadata.get("episode_ms", 0)
            else:
                result_dict["epoch_switches"] = result.epoch_switches
                result_dict["notes"] = result.notes
            
            json.dump(result_dict, f)
            f.write("\n")
    
    # Print summary stats
    total = len(results)
    successes = sum(1 for r in results if r.success)
    over_budget = sum(1 for r in results if r.over_budget)
    avg_tokens = sum(r.tokens_used for r in results) / total if total > 0 else 0
    
    print(f"Policy: {args.policy}")
    print(f"Episodes: {total}")
    print(f"Successes: {successes}/{total} ({100*successes/total:.1f}%)")
    print(f"Over budget: {over_budget}/{total} ({100*over_budget/total:.1f}%)")
    print(f"Avg tokens: {avg_tokens:.0f}")
    
    if args.policy in ["bandit_v1", "apex_dynamic"]:
        # Count switches from appropriate field
        if hasattr(results[0], "metadata") and results[0].metadata:
            total_switches = sum(r.metadata.get("switches", 0) for r in results)
        else:
            total_switches = sum(r.epoch_switches for r in results)
        print(f"Total epoch switches: {total_switches}")
    
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()