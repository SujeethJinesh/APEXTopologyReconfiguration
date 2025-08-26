#!/usr/bin/env python3
"""Test CP bound fixtures for review."""

import json
import tempfile
from pathlib import Path
import subprocess

# Test fixtures
fixtures = [
    {"name": "no_violations", "violations": 0, "total": 12},
    {"name": "rare_violation", "violations": 1, "total": 12},
    {"name": "more_violations", "violations": 3, "total": 12},
]

for fixture in fixtures:
    # Create test data
    test_data = []
    for i in range(fixture["total"]):
        test_data.append({
            "task_id": f"task_{i}",
            "over_budget": i < fixture["violations"]
        })
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "episodes.jsonl"
        output_path = Path(tmpdir) / f"cp_{fixture['name']}.json"
        
        with open(input_path, "w") as f:
            for item in test_data:
                json.dump(item, f)
                f.write("\n")
        
        # Run compute_cp
        result = subprocess.run(
            [
                "python3", "-m", "scripts.compute_cp",
                "--in", str(input_path),
                "--out", str(output_path),
                "--confidence", "0.95",
                "--seed", "42"
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            with open(output_path, "r") as f:
                cp_result = json.load(f)
            
            print(f"\n=== {fixture['name']} ({fixture['violations']}/{fixture['total']}) ===")
            print(json.dumps(cp_result, indent=2))
        else:
            print(f"Error: {result.stderr}")