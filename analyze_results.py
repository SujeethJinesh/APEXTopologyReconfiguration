#!/usr/bin/env python3
"""Analyze APEX evaluation results honestly and create visualizations."""

import json
import sys
from pathlib import Path
from typing import Dict, List
import numpy as np


def load_results(filepath: str) -> Dict:
    """Load results from JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Results file not found: {filepath}")
        print("   Run evaluation first: python3 run_baseline_evaluation.py")
        sys.exit(1)


def analyze_performance(results: Dict) -> Dict:
    """Analyze performance metrics honestly."""
    
    analysis = {
        "summary": {},
        "findings": [],
        "concerns": [],
        "recommendations": []
    }
    
    # Extract policy results
    policies = results.get("results", {})
    
    # Calculate summary statistics
    for policy, data in policies.items():
        # Handle both formats (list of tasks or summary dict)
        if isinstance(data, list):
            # List format - calculate stats
            tasks = data
            successes = sum(1 for t in tasks if t.get("success", False))
            total_tokens = sum(t.get("tokens_used", 0) for t in tasks)
            
            analysis["summary"][policy] = {
                "success_rate": successes / len(tasks) if tasks else 0,
                "avg_tokens": total_tokens / len(tasks) if tasks else 0,
                "total_tasks": len(tasks),
                "tasks": tasks  # Keep task details
            }
        else:
            # Dict format with pre-calculated stats
            analysis["summary"][policy] = {
                "success_rate": data.get("success_rate", 0),
                "avg_tokens": data.get("avg_tokens", 0),
                "total_tasks": len(data.get("tasks", [])),
                "tasks": data.get("tasks", [])
            }
    
    # Honest assessment of results
    success_rates = [d["success_rate"] for d in analysis["summary"].values()]
    token_usages = [d["avg_tokens"] for d in analysis["summary"].values()]
    
    # Check for meaningful differences
    success_variance = np.var(success_rates) if success_rates else 0
    token_variance = np.var(token_usages) if token_usages else 0
    
    # Finding: Success rate analysis
    if max(success_rates) == 0:
        analysis["concerns"].append("⚠️ NO TASKS SUCCEEDED - Critical issue with implementation")
        analysis["recommendations"].append("Debug agent implementation and LLM integration")
    elif success_variance < 0.01:  # Less than 1% variance
        analysis["findings"].append("All topologies have similar success rates")
        analysis["concerns"].append("Topology may not be affecting task success")
    else:
        best_policy = max(analysis["summary"].items(), key=lambda x: x[1]["success_rate"])
        worst_policy = min(analysis["summary"].items(), key=lambda x: x[1]["success_rate"])
        diff = best_policy[1]["success_rate"] - worst_policy[1]["success_rate"]
        analysis["findings"].append(f"{best_policy[0]} performs {diff*100:.1f}% better than {worst_policy[0]}")
    
    # Finding: Token usage analysis
    if token_variance < 10000:  # Less than 100 token difference
        analysis["findings"].append("Token usage is similar across topologies")
        analysis["concerns"].append("Communication patterns may not differ by topology")
    else:
        most_efficient = min(analysis["summary"].items(), key=lambda x: x[1]["avg_tokens"])
        least_efficient = max(analysis["summary"].items(), key=lambda x: x[1]["avg_tokens"])
        savings = least_efficient[1]["avg_tokens"] - most_efficient[1]["avg_tokens"]
        analysis["findings"].append(f"{most_efficient[0]} saves {savings:.0f} tokens vs {least_efficient[0]}")
    
    # Statistical significance check
    n_tasks = analysis["summary"][list(policies.keys())[0]]["total_tasks"]
    if n_tasks < 30:
        analysis["concerns"].append(f"Only {n_tasks} tasks - not statistically significant")
        analysis["recommendations"].append(f"Run with at least 30 tasks for statistical validity")
    
    return analysis


def create_visualization(results: Dict, analysis: Dict):
    """Create simple text-based visualization of results."""
    
    print("\n" + "=" * 80)
    print("APEX EVALUATION ANALYSIS - HONEST ASSESSMENT")
    print("=" * 80)
    
    # Performance table
    print("\n📊 PERFORMANCE METRICS")
    print("-" * 60)
    print(f"{'Policy':<15} {'Success Rate':>15} {'Avg Tokens':>15} {'Tasks':>10}")
    print("-" * 60)
    
    for policy, metrics in analysis["summary"].items():
        success_pct = metrics["success_rate"] * 100
        print(f"{policy:<15} {success_pct:>14.1f}% {metrics['avg_tokens']:>15.0f} {metrics['total_tasks']:>10}")
    
    # Key findings
    print("\n🔍 KEY FINDINGS")
    print("-" * 60)
    if analysis["findings"]:
        for finding in analysis["findings"]:
            print(f"• {finding}")
    else:
        print("• No significant findings yet")
    
    # Concerns
    print("\n⚠️  CONCERNS")
    print("-" * 60)
    if analysis["concerns"]:
        for concern in analysis["concerns"]:
            print(f"• {concern}")
    else:
        print("• No concerns identified")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 60)
    if analysis["recommendations"]:
        for rec in analysis["recommendations"]:
            print(f"• {rec}")
    else:
        print("• Continue testing with current setup")
    
    # Task-level details
    print("\n📋 TASK-LEVEL RESULTS")
    print("-" * 60)
    
    # Get all unique tasks
    all_tasks = set()
    for policy_data in analysis["summary"].values():
        for task_result in policy_data.get("tasks", []):
            task_id = task_result.get("task_id") or task_result.get("task", "unknown")
            all_tasks.add(task_id)
    
    # Show results per task
    for task in sorted(all_tasks):
        print(f"\nTask: {task}")
        for policy, summary in analysis["summary"].items():
            tasks = summary.get("tasks", [])
            task_results = [t for t in tasks if (t.get("task_id") == task or t.get("task") == task)]
            if task_results:
                result = task_results[0]
                success = "✓" if result.get("success", False) else "✗"
                tokens = result.get("tokens_used") or result.get("tokens", 0)
                time = result.get("time", 0)
                print(f"  {policy:<12}: {success} Success | {tokens:>6} tokens | {time:>5.1f}s")
    
    # Statistical analysis
    print("\n📈 STATISTICAL ANALYSIS")
    print("-" * 60)
    
    success_rates = [m["success_rate"] for m in analysis["summary"].values()]
    token_usages = [m["avg_tokens"] for m in analysis["summary"].values()]
    
    if success_rates:
        print(f"Success rate variance: {np.var(success_rates):.4f}")
        print(f"Success rate std dev:  {np.std(success_rates):.4f}")
        
    if token_usages:
        print(f"Token usage variance:  {np.var(token_usages):.0f}")
        print(f"Token usage std dev:   {np.std(token_usages):.0f}")
    
    # Bottom line
    print("\n" + "=" * 80)
    print("BOTTOM LINE")
    print("=" * 80)
    
    if max(success_rates) == 0:
        print("❌ CRITICAL: No tasks succeeded. Fix implementation before drawing conclusions.")
    elif np.var(success_rates) < 0.001 and np.var(token_usages) < 1000:
        print("🔬 No meaningful differences between topologies detected.")
        print("   Possible reasons:")
        print("   1. Generic agents not utilizing topology differences")
        print("   2. Tasks too simple/complex for topology to matter")
        print("   3. Need more tasks for statistical significance")
    else:
        best = max(analysis["summary"].items(), key=lambda x: x[1]["success_rate"])
        print(f"✅ {best[0]} shows best performance: {best[1]['success_rate']*100:.0f}% success rate")
        
        # Check if difference is meaningful
        success_diff = max(success_rates) - min(success_rates)
        if success_diff > 0.1:  # More than 10% difference
            print(f"   This is a meaningful {success_diff*100:.0f}% improvement")
        else:
            print(f"   But only {success_diff*100:.0f}% better than worst - may not be significant")


def main():
    """Main analysis function."""
    
    # Try to load results
    results_file = Path("artifacts/local/baseline_results.json")
    
    if not results_file.exists():
        # Try alternative locations
        alt_files = [
            Path("artifacts/local/apex_evaluation_results.json"),
            Path("artifacts/local/simple_eval_results.json")
        ]
        
        for alt in alt_files:
            if alt.exists():
                results_file = alt
                print(f"Using results from: {alt}")
                break
    
    # Load and analyze
    results = load_results(str(results_file))
    analysis = analyze_performance(results)
    
    # Create visualization
    create_visualization(results, analysis)
    
    # Save analysis
    analysis_file = results_file.parent / "analysis_report.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n📁 Analysis saved to: {analysis_file}")


if __name__ == "__main__":
    main()