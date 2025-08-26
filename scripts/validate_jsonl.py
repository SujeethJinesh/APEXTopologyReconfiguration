#!/usr/bin/env python3
"""Validate that JSONL files are canonical one-object-per-line format."""

import json
import sys
from pathlib import Path


def validate_jsonl(filepath: Path):
    """
    Validate JSONL format.
    Returns (is_valid, line_count, error_msg).
    """
    if not filepath.exists():
        return False, 0, f"File not found: {filepath}"
    
    line_count = 0
    try:
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip('\n')
                if not line:  # Allow empty last line
                    continue
                try:
                    json.loads(line)
                    line_count += 1
                except json.JSONDecodeError as e:
                    return False, line_num, f"Line {line_num}: {e}"
        return True, line_count, "Valid JSONL"
    except Exception as e:
        return False, 0, str(e)


def main():
    if len(sys.argv) > 1:
        # Validate specific file provided as argument
        filepath = Path(sys.argv[1])
        valid, count, msg = validate_jsonl(filepath)
        
        status = "✅ VALID" if valid else "❌ INVALID"
        print(f"{filepath.name:30} {status:10} {count:3} objects")
        if not valid:
            print(f"  Error: {msg}")
            return 1
        return 0
    
    # Default behavior for A3 artifacts
    artifacts_dir = Path("docs/A3/artifacts")
    files = [
        "agents_star_trace.jsonl",
        "agents_chain_trace.jsonl",
        "agents_flat_trace.jsonl",
        "agents_switch_trace.jsonl"
    ]
    
    print("JSONL Validation Report")
    print("=" * 50)
    
    all_valid = True
    for filename in files:
        filepath = artifacts_dir / filename
        valid, count, msg = validate_jsonl(filepath)
        
        status = "✅ VALID" if valid else "❌ INVALID"
        print(f"{filename:30} {status:10} {count:3} objects")
        if not valid:
            print(f"  Error: {msg}")
            all_valid = False
    
    print("=" * 50)
    if all_valid:
        print("✅ All JSONL files are valid one-object-per-line format")
        return 0
    else:
        print("❌ Some files have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())