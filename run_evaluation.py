#!/usr/bin/env python3
"""APEX evaluation runner for testing generic agent collaboration through different topologies."""

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
    """Run APEX evaluation with generic agents on different topologies."""
    
    # Configuration
    N_TASKS = 1  # Start with just 1 task for testing
    BUDGET = 5000  # Smaller budget for quicker testing
    SEED = 42
    
    print("=" * 80)
    print("APEX GENERIC AGENT EVALUATION")
    print("=" * 80)
    print(f"Tasks: {N_TASKS}")
    print(f"Budget: {BUDGET} tokens")
    print(f"Seed: {SEED}")
    print()
    
    # Enable network and LLM for real agent solving
    os.environ["APEX_ALLOW_NETWORK"] = "1"
    os.environ["APEX_ALLOW_LLM"] = "1"
    os.environ["APEX_NUM_LLM_INSTANCES"] = "3"
    
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
    
    # Test each topology configuration
    policies = ["static_star", "static_chain", "static_flat"]
    all_results = {}
    
    print("\n" + "=" * 80)
    print("Running with Real LLM Agents")
    print("Generic agents will collaborate through message passing")
    print("=" * 80)
    
    for policy in policies:
        print(f"\n{'=' * 60}")
        print(f"Testing Topology: {policy}")
        print("=" * 60)
        
        results = []
        
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
                import traceback
                print(f"  Traceback: {traceback.format_exc()}")
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
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    print("\nTopology      | Success Rate | Avg Tokens | Notes")
    print("-" * 70)
    
    for policy in policies:
        results = all_results[policy]
        successes = sum(1 for r in results if r["success"])
        success_rate = successes/len(results)*100 if results else 0
        avg_tokens = sum(r["tokens_used"] for r in results) / len(results) if results else 0
        
        # Determine notes based on results
        if success_rate == 0:
            notes = "No agent solving (test-only)"
        elif success_rate < 30:
            notes = "Low success - needs improvement"
        else:
            notes = "Agents collaborating effectively"
        
        print(f"{policy:13} | {success_rate:11.1f}% | {avg_tokens:10.0f} | {notes}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Integrate MessageSWEAgent for actual collaborative solving")
    print("2. Setup LLM server for agent reasoning")
    print("3. Test dynamic topology switching with APEX controller")
    print("4. Measure performance differences between topologies")
    
    return all_results


if __name__ == "__main__":
    results = asyncio.run(main())