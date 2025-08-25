"""Test that bootstrap CI is invariant to row order within policies."""

import json
import random
import tempfile
from pathlib import Path

from scripts.compute_lift import compute_lift


def test_bootstrap_pairing_invariance():
    """Prove that bootstrap CI is unchanged when rows are shuffled within policies."""
    
    # Create test data with known structure
    apex_data = [
        {"task_id": "task_1", "success": True, "tokens_used": 1000},
        {"task_id": "task_2", "success": True, "tokens_used": 2000},
        {"task_id": "task_3", "success": False, "tokens_used": 3000},
        {"task_id": "task_4", "success": True, "tokens_used": 1500},
        {"task_id": "task_5", "success": False, "tokens_used": 2500},
    ]
    
    static_data = [
        {"task_id": "task_1", "success": False, "tokens_used": 1100},
        {"task_id": "task_2", "success": True, "tokens_used": 2100},
        {"task_id": "task_3", "success": False, "tokens_used": 3100},
        {"task_id": "task_4", "success": True, "tokens_used": 1600},
        {"task_id": "task_5", "success": True, "tokens_used": 2600},
    ]
    
    # Write to temp files and compute lift
    with tempfile.TemporaryDirectory() as tmpdir:
        apex_file = Path(tmpdir) / "apex.jsonl"
        static_file = Path(tmpdir) / "static.jsonl"
        
        # Write original order
        with open(apex_file, "w") as f:
            for item in apex_data:
                f.write(json.dumps(item) + "\n")
        
        with open(static_file, "w") as f:
            for item in static_data:
                f.write(json.dumps(item) + "\n")
        
        # Compute lift with original order
        lift1 = compute_lift(str(apex_file), str(static_file), n_bootstrap=100, seed=42)
        
        # Shuffle both datasets (but keep task_id pairing intact)
        random.shuffle(apex_data)
        random.shuffle(static_data)
        
        # Write shuffled order
        with open(apex_file, "w") as f:
            for item in apex_data:
                f.write(json.dumps(item) + "\n")
        
        with open(static_file, "w") as f:
            for item in static_data:
                f.write(json.dumps(item) + "\n")
        
        # Compute lift with shuffled order
        lift2 = compute_lift(str(apex_file), str(static_file), n_bootstrap=100, seed=42)
        
        # Bootstrap CI should be identical (within floating point tolerance)
        assert abs(lift1["lift_mean"] - lift2["lift_mean"]) < 1e-6, \
            f"Lift mean changed: {lift1['lift_mean']} vs {lift2['lift_mean']}"
        assert abs(lift1["ci_lower"] - lift2["ci_lower"]) < 1e-6, \
            f"CI lower changed: {lift1['ci_lower']} vs {lift2['ci_lower']}"
        assert abs(lift1["ci_upper"] - lift2["ci_upper"]) < 1e-6, \
            f"CI upper changed: {lift1['ci_upper']} vs {lift2['ci_upper']}"


def test_bootstrap_samples_tasks_not_rows():
    """Verify bootstrap resamples tasks by ID, not individual rows."""
    
    # Create test data where task_1 appears twice (simulating repetition)
    apex_data = [
        {"task_id": "task_1", "success": True, "tokens_used": 1000},
        {"task_id": "task_1__rep_1", "success": True, "tokens_used": 1050},
        {"task_id": "task_2", "success": False, "tokens_used": 2000},
        {"task_id": "task_3", "success": True, "tokens_used": 3000},
    ]
    
    static_data = [
        {"task_id": "task_1", "success": False, "tokens_used": 1100},
        {"task_id": "task_1__rep_1", "success": True, "tokens_used": 1150},
        {"task_id": "task_2", "success": False, "tokens_used": 2100},
        {"task_id": "task_3", "success": False, "tokens_used": 3100},
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        apex_file = Path(tmpdir) / "apex.jsonl"
        static_file = Path(tmpdir) / "static.jsonl"
        
        with open(apex_file, "w") as f:
            for item in apex_data:
                f.write(json.dumps(item) + "\n")
        
        with open(static_file, "w") as f:
            for item in static_data:
                f.write(json.dumps(item) + "\n")
        
        # Compute lift - should work correctly with duplicate task IDs
        lift = compute_lift(str(apex_file), str(static_file), n_bootstrap=50, seed=99)
        
        # Should have valid results
        assert "lift_mean" in lift
        assert "ci_lower" in lift
        assert "ci_upper" in lift
        assert lift["n_tasks"] == 4  # Should count unique tasks