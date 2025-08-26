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
        "--policy",
        choices=["static_star", "static_chain", "static_flat", "bandit_v1"],
        required=True,
        help="Policy to evaluate"
    )
    parser.add_argument("--out", type=str, required=True, help="Output JSONL file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    # Mode selection
    parser.add_argument(
        "--mode",
        choices=["stub", "swe"],
        default="stub",
        help="Evaluation mode: stub (CI) or swe (SWE-bench Lite)"
    )
    
    # SWE-specific options
    parser.add_argument(
        "--split",
        choices=["dev", "test"],
        default="dev",
        help="SWE-bench Lite split to use (dev=23, test=300 tasks)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks from dataset"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local cache only, no network access"
    )
    parser.add_argument(
        "--oracle-smoke",
        action="store_true",
        help="Apply gold patch for validation testing"
    )
    
    args = parser.parse_args()
    
    # Network gating check for SWE mode
    if args.mode == "swe" and not args.offline:
        import os
        if os.getenv("APEX_ALLOW_NETWORK") != "1":
            print("Error: SWE mode requires network access.")
            print("Either set APEX_ALLOW_NETWORK=1 or use --offline with fixtures.")
            sys.exit(1)
    
    # Initialize harness
    harness = EvalHarness(
        mode=args.mode,
        seed=args.seed,
        split=args.split,
        limit=args.limit,
        offline=args.offline,
        oracle_smoke=args.oracle_smoke,
    )
    
    # Load tasks
    tasks = harness.load_tasks(n_episodes=args.episodes)
    
    # Setup switch and bandit for dynamic policy
    switch = None
    bandit = None
    if args.policy == "bandit_v1":
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
            json.dump(result.to_dict(), f)
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
    
    if args.policy == "bandit_v1":
        total_switches = sum(r.epoch_switches for r in results)
        print(f"Total epoch switches: {total_switches}")
    
    print(f"Output written to: {output_path}")
    
    # Clean up SWE workspace if used
    if args.mode == "swe":
        harness.cleanup()


if __name__ == "__main__":
    main()