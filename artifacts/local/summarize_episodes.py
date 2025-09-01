#!/usr/bin/env python3
"""Summarize episode results from JSONL."""
import json
import sys
from pathlib import Path

def summarize(jsonl_path):
    records = []
    with open(jsonl_path) as f:
        for line in f:
            records.append(json.loads(line))
    
    print(f"Episodes: {len(records)}")
    for i, r in enumerate(records[:5]):  # First 5
        status = "✅" if r["success"] else "❌"
        print(f"{i+1}. {r['task_id']}: {status} tokens={r['tokens_used']}, switches={r.get('epoch_switches', 0)}")
    
    successes = sum(1 for r in records if r["success"])
    tokens = sum(r["tokens_used"] for r in records)
    print(f"\nSummary: {successes}/{len(records)} success, avg={tokens//len(records)} tokens")

if __name__ == "__main__":
    summarize(sys.argv[1] if len(sys.argv) > 1 else "artifacts/local/real_n1_bandit_swe.jsonl")
