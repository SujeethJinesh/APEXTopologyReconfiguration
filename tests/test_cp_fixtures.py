"""Test Clopper-Pearson implementation with known values."""

import json
import tempfile
from pathlib import Path

from scripts.compute_cp import compute_cp, clopper_pearson_upper


def test_cp_formula_fixtures():
    """Verify CP upper bound matches expected values for known inputs."""
    
    # Test fixtures with expected values (computed independently)
    fixtures = [
        # (violations, total, expected_upper_bound)
        (0, 12, 0.2211),  # No violations in 12 trials -> ~22.11% upper bound
        (1, 12, 0.3327),  # 1 violation in 12 trials -> ~33.27% upper bound
        (3, 12, 0.5438),  # 3 violations in 12 trials -> ~54.38% upper bound
        (0, 100, 0.0295), # No violations in 100 trials -> ~2.95% upper bound
        (5, 100, 0.0940), # 5 violations in 100 trials -> ~9.40% upper bound
    ]
    
    for violations, total, expected in fixtures:
        actual = clopper_pearson_upper(violations, total)
        assert abs(actual - expected) < 1e-3, \
            f"CP({violations}/{total}) = {actual:.4f}, expected {expected:.4f}"


def test_cp_zero_violations_special_case():
    """Test that zero violations is handled correctly."""
    
    # With 0 violations out of n trials, upper bound = 1 - (0.05)^(1/n)
    test_cases = [
        (10, 0.2589),  # 0/10 -> ~25.89%
        (20, 0.1392),  # 0/20 -> ~13.92%
        (50, 0.0580),  # 0/50 -> ~5.80%
        (100, 0.0295), # 0/100 -> ~2.95%
    ]
    
    for n, expected in test_cases:
        actual = clopper_pearson_upper(0, n)
        assert abs(actual - expected) < 1e-3, \
            f"CP(0/{n}) = {actual:.4f}, expected {expected:.4f}"


def test_cp_from_jsonl():
    """Test CP computation from JSONL data."""
    
    # Create test data with known violations
    data = [
        {"task_id": "task_1", "over_budget": False},
        {"task_id": "task_2", "over_budget": True},   # violation
        {"task_id": "task_3", "over_budget": False},
        {"task_id": "task_4", "over_budget": False},
        {"task_id": "task_5", "over_budget": True},   # violation
        {"task_id": "task_6", "over_budget": False},
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_file = Path(tmpdir) / "test.jsonl"
        
        with open(jsonl_file, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        
        # Compute CP bound
        result = compute_cp(str(jsonl_file))
        
        # Should have 2 violations out of 6
        assert result["violations"] == 2
        assert result["total"] == 6
        assert result["violation_rate"] == 2/6
        
        # CP upper bound for 2/6 should be around 0.6582
        assert abs(result["cp_upper_95"] - 0.6582) < 1e-3


def test_cp_respects_confidence_level():
    """Verify CP bound increases with confidence level."""
    
    # Same data, different confidence levels
    violations = 1
    total = 10
    
    cp_90 = clopper_pearson_upper(violations, total, confidence=0.90)
    cp_95 = clopper_pearson_upper(violations, total, confidence=0.95)
    cp_99 = clopper_pearson_upper(violations, total, confidence=0.99)
    
    # Higher confidence -> higher upper bound
    assert cp_90 < cp_95 < cp_99, \
        f"Expected monotonic: {cp_90:.4f} < {cp_95:.4f} < {cp_99:.4f}"
    
    # Check approximate values
    assert abs(cp_90 - 0.2658) < 1e-3  # 1/10 at 90% confidence
    assert abs(cp_95 - 0.3088) < 1e-3  # 1/10 at 95% confidence
    assert abs(cp_99 - 0.3870) < 1e-3  # 1/10 at 99% confidence