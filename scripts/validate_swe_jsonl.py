#!/usr/bin/env python3
"""Validate SWE-bench JSONL result files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple, List


def validate_jsonl(filepath: Path) -> Tuple[bool, int, str]:
    """
    Validate JSONL format and check required fields.
    Returns (is_valid, line_count, error_msg).
    """
    if not filepath.exists():
        return False, 0, f"File not found: {filepath}"
    
    # Accept both old and new field names for compatibility
    required_fields = ["task_id", "policy", "success", "budget", "seed"]
    line_count = 0
    
    try:
        with open(filepath, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip("\n")
                if not line:  # Allow empty last line
                    continue
                try:
                    obj = json.loads(line)
                    
                    # Skip metadata lines
                    if "__meta__" in obj:
                        continue
                    
                    line_count += 1
                    
                    # Check required fields
                    for field in required_fields:
                        if field not in obj:
                            return False, line_num, f"Line {line_num}: Missing required field '{field}'"
                    
                    # Basic type checks
                    if not isinstance(obj["success"], bool):
                        return False, line_num, f"Line {line_num}: 'success' must be boolean"
                    
                    # Check for either tokens_used or tokens_used_total
                    if "tokens_used" not in obj and "tokens_used_total" not in obj:
                        return False, line_num, f"Line {line_num}: Missing 'tokens_used' or 'tokens_used_total'"
                    
                    tokens_field = "tokens_used_total" if "tokens_used_total" in obj else "tokens_used"
                    if not isinstance(obj[tokens_field], (int, float)):
                        return False, line_num, f"Line {line_num}: '{tokens_field}' must be numeric"
                    
                    # Check for either over_budget or budget_violated
                    budget_field = None
                    if "budget_violated" in obj:
                        budget_field = "budget_violated"
                    elif "over_budget" in obj:
                        budget_field = "over_budget"
                    else:
                        return False, line_num, f"Line {line_num}: Missing 'budget_violated' or 'over_budget'"
                    
                    if not isinstance(obj[budget_field], bool):
                        return False, line_num, f"Line {line_num}: '{budget_field}' must be boolean"
                        
                except json.JSONDecodeError as e:
                    return False, line_num, f"Line {line_num}: JSON decode error: {e}"
        
        return True, line_count, "Valid JSONL with all required fields"
    
    except Exception as e:
        return False, 0, str(e)


def validate_task_list_match(jsonl_files: List[Path], task_list_file: Path) -> Tuple[bool, str]:
    """Validate that all JSONL files have identical task_id sets matching the task list.
    
    Returns:
        (is_valid, message) tuple
    """
    # Load task list
    expected_tasks = set()
    with open(task_list_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                # Skip metadata lines
                if "__meta__" in entry:
                    continue
                if "task_id" in entry:
                    expected_tasks.add(entry["task_id"])
    
    # Check each JSONL file
    all_task_sets = {}
    for filepath in jsonl_files:
        task_ids = set()
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    # Skip metadata lines
                    if "__meta__" in obj:
                        continue
                    task_ids.add(obj["task_id"])
        all_task_sets[filepath.name] = task_ids
    
    # Verify all files have identical task sets
    first_set = None
    for filename, task_set in all_task_sets.items():
        if first_set is None:
            first_set = task_set
        elif task_set != first_set:
            diff = task_set.symmetric_difference(first_set)
            return False, f"Task ID mismatch in {filename}: {diff}"
    
    # Verify task set matches expected list
    if first_set != expected_tasks:
        missing = expected_tasks - first_set
        extra = first_set - expected_tasks
        msg = []
        if missing:
            msg.append(f"Missing tasks: {missing}")
        if extra:
            msg.append(f"Extra tasks: {extra}")
        return False, "; ".join(msg)
    
    return True, f"All files have identical task sets ({len(expected_tasks)} tasks)"


def main():
    parser = argparse.ArgumentParser(description="Validate SWE-bench JSONL files")
    parser.add_argument("file", nargs="?", help="Path to JSONL file to validate")
    parser.add_argument("--inputs", nargs="+", help="Multiple JSONL files to validate")
    parser.add_argument("--task-list", help="Path to task list JSONL for validation")
    parser.add_argument("--expect-n", type=int, help="Expected number of tasks (excluding metadata)")
    parser.add_argument("--strict-provenance", help="Require provenance.source to match this value")
    parser.add_argument("--print-summary", action="store_true", help="Print summary statistics")
    args = parser.parse_args()
    
    # Multi-file validation with task list
    if args.inputs and args.task_list:
        input_files = [Path(f) for f in args.inputs]
        task_list_file = Path(args.task_list)
        
        # First validate each file individually
        print("Individual file validation:")
        print("-" * 50)
        all_valid = True
        task_counts = {}
        for filepath in input_files:
            valid, count, msg = validate_jsonl(filepath)
            status = "✅" if valid else "❌"
            task_counts[filepath.name] = count
            print(f"{filepath.name:30} {status} {count:3} records")
            if not valid:
                print(f"  Error: {msg}")
                all_valid = False
            
            # Check expected count
            if args.expect_n and count != args.expect_n:
                print(f"  Error: Expected {args.expect_n} tasks, got {count}")
                all_valid = False
            
            # Check provenance if strict mode
            if args.strict_provenance:
                with open(filepath, 'r') as f:
                    for line in f:
                        obj = json.loads(line)
                        if "__meta__" in obj:
                            continue
                        if "provenance" in obj:
                            source = obj["provenance"].get("source", "")
                            if source != args.strict_provenance:
                                print(f"  Error: provenance.source='{source}' != '{args.strict_provenance}'")
                                all_valid = False
                                break
                        break  # Only check first data record
        
        if not all_valid:
            print("\n❌ Some files have format issues")
            return 1
        
        # Then validate task list match
        print("\nTask list validation:")
        print("-" * 50)
        valid, msg = validate_task_list_match(input_files, task_list_file)
        if valid:
            print(f"✅ {msg}")
        else:
            print(f"❌ {msg}")
            return 1
        
        # Print summary if requested
        if args.print_summary:
            print("\nSummary Statistics:")
            print("-" * 50)
            for name, count in task_counts.items():
                print(f"{name:30} {count:3} tasks")
            if args.strict_provenance:
                print(f"Provenance: {args.strict_provenance}")
        
        return 0
    
    # Single file validation
    elif args.file:
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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())