#!/usr/bin/env python3
"""Validate SWE-bench JSONL result files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple


def validate_jsonl(filepath: Path) -> Tuple[bool, int, str]:
    """
    Validate JSONL format and check required fields.
    Returns (is_valid, line_count, error_msg).
    """
    if not filepath.exists():
        return False, 0, f"File not found: {filepath}"
    
    required_fields = ["task_id", "policy", "success", "tokens_used", "over_budget", "budget", "seed"]
    line_count = 0
    
    try:
        with open(filepath, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip("\n")
                if not line:  # Allow empty last line
                    continue
                try:
                    obj = json.loads(line)
                    line_count += 1
                    
                    # Check required fields
                    for field in required_fields:
                        if field not in obj:
                            return False, line_num, f"Line {line_num}: Missing required field '{field}'"
                    
                    # Basic type checks
                    if not isinstance(obj["success"], bool):
                        return False, line_num, f"Line {line_num}: 'success' must be boolean"
                    if not isinstance(obj["tokens_used"], (int, float)):
                        return False, line_num, f"Line {line_num}: 'tokens_used' must be numeric"
                    if not isinstance(obj["over_budget"], bool):
                        return False, line_num, f"Line {line_num}: 'over_budget' must be boolean"
                        
                except json.JSONDecodeError as e:
                    return False, line_num, f"Line {line_num}: JSON decode error: {e}"
        
        return True, line_count, "Valid JSONL with all required fields"
    
    except Exception as e:
        return False, 0, str(e)


def main():
    parser = argparse.ArgumentParser(description="Validate SWE-bench JSONL files")
    parser.add_argument("file", help="Path to JSONL file to validate")
    args = parser.parse_args()
    
    filepath = Path(args.file)
    valid, count, msg = validate_jsonl(filepath)
    
    print(f"Validating: {filepath.name}")
    print("-" * 50)
    
    if valid:
        print(f"✅ VALID: {count} records")
        print(f"   {msg}")
        return 0
    else:
        print(f"❌ INVALID")
        print(f"   {msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())