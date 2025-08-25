#!/usr/bin/env python3
"""Validate A5 JSONL files."""

import json
import sys
from pathlib import Path

def validate_jsonl(filepath):
    """Validate a JSONL file."""
    try:
        count = 0
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():  # Skip empty lines
                    try:
                        obj = json.loads(line)
                        count += 1
                    except json.JSONDecodeError as e:
                        return False, f"Line {line_num}: {e}"
        return True, f"{count} objects"
    except Exception as e:
        return False, str(e)

# Check all A5 JSONL files
files = [
    "docs/A5/artifacts/static_star.jsonl",
    "docs/A5/artifacts/static_chain.jsonl", 
    "docs/A5/artifacts/static_flat.jsonl",
    "docs/A5/artifacts/static_best.jsonl",
    "docs/A5/artifacts/apex_dynamic.jsonl"
]

print("A5 JSONL Validation Report")
print("=" * 50)

all_valid = True
for filepath in files:
    path = Path(filepath)
    if path.exists():
        valid, msg = validate_jsonl(path)
        status = "✅ VALID" if valid else "❌ INVALID"
        filename = path.name
        print(f"{filename:25} {status:12} {msg}")
        if not valid:
            all_valid = False
    else:
        print(f"{path.name:25} ❌ NOT FOUND")
        all_valid = False

print("=" * 50)
if all_valid:
    print("✅ All A5 JSONL files are valid one-object-per-line format")
else:
    print("❌ Some files have issues")
    sys.exit(1)