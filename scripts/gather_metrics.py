#!/usr/bin/env python3
"""Gather metrics from evaluation results."""

import json
import sys
from pathlib import Path

def analyze_file(filepath):
    """Analyze a JSONL result file."""
    successes = 0
    violations = 0 
    total_tokens = 0
    count = 0
    
    with open(filepath, "r") as f:
        for line in f:
            result = json.loads(line)
            count += 1
            if result["success"]:
                successes += 1
            if result["over_budget"]:
                violations += 1
            total_tokens += result["tokens_used"]
    
    return {
        "success_rate": successes / count if count else 0,
        "violation_rate": violations / count if count else 0,
        "avg_tokens": total_tokens / count if count else 0,
        "count": count,
        "successes": successes,
        "violations": violations
    }

if __name__ == "__main__":
    # Analyze each file
    files = {
        "static_star": "docs/A5/artifacts/swe/dev/static_star_dev_sample100.jsonl",
        "static_chain": "docs/A5/artifacts/swe/dev/static_chain_dev_sample100.jsonl",
        "static_flat": "docs/A5/artifacts/swe/dev/static_flat_dev_sample100.jsonl",
        "static_best": "docs/A5/artifacts/swe/dev/static_best_dev_sample100.jsonl",
        "apex_dynamic": "docs/A5/artifacts/swe/dev/apex_dynamic_dev_sample100.jsonl"
    }
    
    for name, filepath in files.items():
        stats = analyze_file(filepath)
        print(f"\n{name}:")
        print(f"  Success: {stats['successes']}/{stats['count']} ({stats['success_rate']:.1%})")
        print(f"  Violations: {stats['violations']}/{stats['count']} ({stats['violation_rate']:.1%})")
        print(f"  Avg tokens: {stats['avg_tokens']:.0f}")