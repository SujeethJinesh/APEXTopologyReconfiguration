#!/usr/bin/env python3
"""Test that static_best is properly selected from only static policies."""

import json
from pathlib import Path


def test_best_static_only_from_static_policies():
    """Prove static_best_test300.jsonl is selected only from {star, chain, flat}."""
    best_path = Path("docs/A5/artifacts/swe/test/static_best_test300.jsonl")
    
    if not best_path.exists():
        import pytest
        pytest.skip("Best static file not found (expected in full run)")
    
    # Load best static results
    with open(best_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            if "__meta__" in obj:
                continue
            
            # Check original_policy field (added by pick_best_static.py)
            if "original_policy" in obj:
                assert obj["original_policy"] in ["static_star", "static_chain", "static_flat"], \
                    f"Invalid original policy: {obj['original_policy']}"
            
            # The policy field should be "static_best"
            assert obj["policy"] == "static_best", \
                f"Best static should have policy='static_best', got {obj['policy']}"
            
            # Notes should indicate which static was selected
            if "notes" in obj and obj["notes"]:
                assert any(p in obj["notes"] for p in ["static_star", "static_chain", "static_flat"]), \
                    f"Notes should mention selected static policy: {obj['notes']}"


def test_no_dynamic_leakage_in_best_static():
    """Ensure no APEX/dynamic results leaked into best static selection."""
    best_path = Path("docs/A5/artifacts/swe/test/static_best_test300.jsonl")
    
    if not best_path.exists():
        import pytest
        pytest.skip("Best static file not found (expected in full run)")
    
    # Check that no dynamic-specific fields are present
    with open(best_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            if "__meta__" in obj:
                continue
            
            # Dynamic policies have epoch_switches > 0
            if "epoch_switches" in obj:
                assert obj["epoch_switches"] == 0, \
                    f"Best static should not have epoch switches, got {obj['epoch_switches']}"
            
            # Check no dynamic policy names
            if "original_policy" in obj:
                assert "bandit" not in obj["original_policy"].lower(), \
                    "Dynamic policy leaked into best static"
                assert "apex" not in obj["original_policy"].lower(), \
                    "APEX policy leaked into best static"
                assert "dynamic" not in obj["original_policy"].lower(), \
                    "Dynamic policy leaked into best static"


def test_best_static_selection_stats():
    """Verify best static selection statistics are reasonable."""
    best_path = Path("docs/A5/artifacts/swe/test/static_best_test300.jsonl")
    
    if not best_path.exists():
        import pytest
        pytest.skip("Best static file not found (expected in full run)")
    
    policy_counts = {"static_star": 0, "static_chain": 0, "static_flat": 0}
    total = 0
    
    with open(best_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            if "__meta__" in obj:
                continue
            
            total += 1
            if "original_policy" in obj:
                policy = obj["original_policy"]
                if policy in policy_counts:
                    policy_counts[policy] += 1
    
    assert total == 300, f"Should have 300 tasks, got {total}"
    
    # At least one policy should be selected
    assert sum(policy_counts.values()) == 300, \
        "Sum of selections should equal total tasks"
    
    # No single policy should dominate completely (sanity check)
    for policy, count in policy_counts.items():
        assert count < 300, f"{policy} selected for all tasks - likely an error"
    
    # At least two policies should be used (realistic expectation)
    policies_used = sum(1 for count in policy_counts.values() if count > 0)
    assert policies_used >= 2, \
        f"Only {policies_used} policy used - expected mix of policies"