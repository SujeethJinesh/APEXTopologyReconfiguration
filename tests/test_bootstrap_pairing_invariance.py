"""Test that bootstrap pairing is invariant to row order."""

from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path
import subprocess


def test_pairing_invariance():
    """Test that lift CI is invariant to row shuffling (within Monte Carlo noise)."""
    
    # Create test data with specific task_ids
    apex_data = [
        {"task_id": "task_A", "success": True, "tokens_used": 100},
        {"task_id": "task_B", "success": False, "tokens_used": 200},
        {"task_id": "task_C", "success": True, "tokens_used": 150},
        {"task_id": "task_D", "success": True, "tokens_used": 180},
        {"task_id": "task_E", "success": False, "tokens_used": 220},
    ]
    
    static_data = [
        {"task_id": "task_A", "success": False, "tokens_used": 110},
        {"task_id": "task_B", "success": False, "tokens_used": 210},
        {"task_id": "task_C", "success": True, "tokens_used": 160},
        {"task_id": "task_D", "success": False, "tokens_used": 190},
        {"task_id": "task_E", "success": True, "tokens_used": 230},
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Original order
        apex_path_1 = Path(tmpdir) / "apex_1.jsonl"
        static_path_1 = Path(tmpdir) / "static_1.jsonl"
        output_1 = Path(tmpdir) / "lift_1.json"
        
        with open(apex_path_1, "w") as f:
            for item in apex_data:
                json.dump(item, f)
                f.write("\n")
        
        with open(static_path_1, "w") as f:
            for item in static_data:
                json.dump(item, f)
                f.write("\n")
        
        # Shuffled order
        apex_shuffled = apex_data.copy()
        static_shuffled = static_data.copy()
        random.seed(12345)  # Different seed for shuffling
        random.shuffle(apex_shuffled)
        random.shuffle(static_shuffled)
        
        apex_path_2 = Path(tmpdir) / "apex_2.jsonl"
        static_path_2 = Path(tmpdir) / "static_2.jsonl"
        output_2 = Path(tmpdir) / "lift_2.json"
        
        with open(apex_path_2, "w") as f:
            for item in apex_shuffled:
                json.dump(item, f)
                f.write("\n")
        
        with open(static_path_2, "w") as f:
            for item in static_shuffled:
                json.dump(item, f)
                f.write("\n")
        
        # Run lift computation with same seed and high bootstrap count
        n_bootstrap = 5000
        seed = 42
        
        for apex_path, static_path, output_path in [
            (apex_path_1, static_path_1, output_1),
            (apex_path_2, static_path_2, output_2),
        ]:
            result = subprocess.run(
                [
                    "python3", "-m", "scripts.compute_lift",
                    "--a", str(apex_path),
                    "--b", str(static_path),
                    "--out", str(output_path),
                    "--paired",
                    "--n-bootstrap", str(n_bootstrap),
                    "--seed", str(seed)
                ],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"compute_lift failed: {result.stderr}"
        
        # Load results
        with open(output_1, "r") as f:
            lift_1 = json.load(f)
        
        with open(output_2, "r") as f:
            lift_2 = json.load(f)
        
        # Check invariance
        print(f"Bootstrap samples: {n_bootstrap}")
        print(f"Random seed: {seed}")
        print()
        print("Original order:")
        print(f"  Lift: {lift_1['lift_abs']:.4f}")
        print(f"  CI: [{lift_1['ci_low']:.4f}, {lift_1['ci_high']:.4f}]")
        print()
        print("Shuffled order:")
        print(f"  Lift: {lift_2['lift_abs']:.4f}")
        print(f"  CI: [{lift_2['ci_low']:.4f}, {lift_2['ci_high']:.4f}]")
        print()
        
        # Should be identical (deterministic with same seed)
        assert lift_1["lift_abs"] == lift_2["lift_abs"], "Lift should be invariant to row order"
        assert lift_1["ci_low"] == lift_2["ci_low"], "CI lower should be invariant"
        assert lift_1["ci_high"] == lift_2["ci_high"], "CI upper should be invariant"
        
        print("✓ Pairing is correctly invariant to row order")


if __name__ == "__main__":
    test_pairing_invariance()