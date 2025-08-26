"""Test JSONL validation for all A5 artifacts."""

import os
import subprocess
from pathlib import Path


def test_validate_a5_jsonl_artifacts():
    """Run JSONL validator on all A5 artifact files and assert they're valid."""
    
    # Path to artifacts directory
    artifacts_dir = Path("docs/A5/artifacts")
    
    # List of expected JSONL files
    expected_files = [
        "static_star.jsonl",
        "static_chain.jsonl",
        "static_flat.jsonl",
        "static_best.jsonl",
        "apex_dynamic.jsonl"
    ]
    
    # Path to validator script
    validator_script = Path("scripts/validate_jsonl.py")
    
    # Ensure validator exists
    assert validator_script.exists(), f"Validator script not found: {validator_script}"
    
    # Validate each file
    for filename in expected_files:
        filepath = artifacts_dir / filename
        
        # Check file exists
        assert filepath.exists(), f"Artifact file not found: {filepath}"
        
        # Run validator
        result = subprocess.run(
            ["python3", str(validator_script), str(filepath)],
            capture_output=True,
            text=True
        )
        
        # Check validator succeeded
        assert result.returncode == 0, \
            f"Validation failed for {filename}: {result.stderr}"
        
        # Check output contains VALID
        assert "VALID" in result.stdout, \
            f"Expected 'VALID' in output for {filename}, got: {result.stdout}"


def test_jsonl_schema_compliance():
    """Verify JSONL files comply with JSON Lines specification."""
    
    import json
    
    artifacts_dir = Path("docs/A5/artifacts")
    jsonl_files = list(artifacts_dir.glob("*.jsonl"))
    
    assert len(jsonl_files) >= 5, f"Expected at least 5 JSONL files, found {len(jsonl_files)}"
    
    for filepath in jsonl_files:
        with open(filepath, "r") as f:
            lines = f.readlines()
            
            # Check each line is valid JSON
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line:  # Skip empty lines at end
                    continue
                    
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise AssertionError(
                        f"{filepath.name} line {i} is not valid JSON: {e}\nLine: {line}"
                    )
                
                # Verify required fields for task results
                required_fields = ["task_id", "policy", "success", "tokens_used", "budget"]
                for field in required_fields:
                    assert field in obj, \
                        f"{filepath.name} line {i} missing field '{field}'"
                
                # Verify types
                assert isinstance(obj["task_id"], str), \
                    f"{filepath.name} line {i}: task_id must be string"
                assert isinstance(obj["success"], bool), \
                    f"{filepath.name} line {i}: success must be boolean"
                assert isinstance(obj["tokens_used"], int), \
                    f"{filepath.name} line {i}: tokens_used must be integer"
                assert isinstance(obj["budget"], int), \
                    f"{filepath.name} line {i}: budget must be integer"


def test_unique_task_ids_in_artifacts():
    """Verify task IDs are unique within each JSONL artifact."""
    
    import json
    
    artifacts_dir = Path("docs/A5/artifacts")
    jsonl_files = [
        "static_star.jsonl",
        "static_chain.jsonl", 
        "static_flat.jsonl",
        "apex_dynamic.jsonl"
    ]
    
    for filename in jsonl_files:
        filepath = artifacts_dir / filename
        
        if not filepath.exists():
            continue  # Skip if file doesn't exist yet
            
        task_ids = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    task_ids.append(obj["task_id"])
        
        # Check all task IDs are unique
        assert len(task_ids) == len(set(task_ids)), \
            f"Duplicate task IDs found in {filename}"
        
        # Verify __rep_ suffixes appear for n > 12
        if len(task_ids) > 12:
            rep_count = sum(1 for tid in task_ids if "__rep_" in tid)
            assert rep_count > 0, \
                f"Expected __rep_ suffixes in {filename} with {len(task_ids)} tasks"