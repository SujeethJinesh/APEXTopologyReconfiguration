#!/usr/bin/env python3
"""Simple evaluation runner for 3 SWE-bench tasks."""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from apex.eval.harness import EvalHarness

async def main():
    """Run simplified evaluation."""
    
    # Configuration
    N_TASKS = 3
    BUDGET = 32000
    SEED = 42
    
    print("=" * 80)
    print("SIMPLIFIED SWE-BENCH EVALUATION")
    print("=" * 80)
    print(f"Tasks: {N_TASKS}")
    print(f"Budget: {BUDGET}")
    print(f"Seed: {SEED}")
    print()
    
    # Always enable LLM and network for evaluations
    os.environ["APEX_ALLOW_NETWORK"] = "1"
    os.environ["APEX_ALLOW_LLM"] = "1"
    
    # Create harness
    print("[INIT] Creating harness...")
    harness = EvalHarness(
        seed=SEED,
        split="dev",
        limit=N_TASKS,
        offline=False,
    )
    
    # Load tasks
    print("[INIT] Loading tasks...")
    tasks = harness.load_tasks(n_episodes=N_TASKS)
    print(f"[INIT] Loaded {len(tasks)} tasks")
    
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task.task_id}")
    
    # Test each policy
    policies = ["static_star", "static_chain", "static_flat"]
    all_results = {}
    
    for policy in policies:
        print(f"\n{'=' * 60}")
        print(f"Testing: {policy}")
        print("=" * 60)
        
        results = []
        
        # Static policies only (no dynamic switch needed)
        
        for task in tasks:
            print(f"\n[{policy}] Task: {task.task_id}")
            start = time.time()
            
            try:
                result = harness.run_episode(
                    task=task,
                    policy=policy,
                    budget=BUDGET,
                )
                
                elapsed = time.time() - start
                
                print(f"  Success: {result.success}")
                print(f"  Tokens: {result.tokens_used}")
                print(f"  Time: {elapsed:.2f}s")
                
                results.append({
                    "task_id": task.task_id,
                    "policy": policy,
                    "success": result.success,
                    "tokens_used": result.tokens_used,
                    "time": elapsed,
                })
                
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({
                    "task_id": task.task_id,
                    "policy": policy,
                    "success": False,
                    "tokens_used": BUDGET,
                    "time": 0,
                    "error": str(e),
                })
        
        all_results[policy] = results
        
        # Summary for this policy
        successes = sum(1 for r in results if r["success"])
        avg_tokens = sum(r["tokens_used"] for r in results) / len(results) if results else 0
        print(f"\n[{policy}] Summary:")
        print(f"  Success rate: {successes}/{len(results)} ({successes/len(results)*100:.0f}%)")
        print(f"  Avg tokens: {avg_tokens:.0f}")
    
    # Clean up
    harness.cleanup()
    
    # Save results
    output_file = Path("artifacts/local/simple_eval_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump({
            "config": {
                "n_tasks": N_TASKS,
                "budget": BUDGET,
                "seed": SEED,
                "timestamp": datetime.now().isoformat(),
            },
            "results": all_results,
        }, f, indent=2)
    
    print(f"\n[SAVED] Results to {output_file}")
    
    # Final comparison
    print("\n" + "=" * 80)
    print("FINAL COMPARISON")
    print("=" * 80)
    
    for policy in policies:
        results = all_results[policy]
        successes = sum(1 for r in results if r["success"])
        avg_tokens = sum(r["tokens_used"] for r in results) / len(results)
        
        print(f"\n{policy}:")
        print(f"  Success: {successes}/{len(results)} ({successes/len(results)*100:.0f}%)")
        print(f"  Tokens: {avg_tokens:.0f}")
    
    return all_results


if __name__ == "__main__":
    results = asyncio.run(main())