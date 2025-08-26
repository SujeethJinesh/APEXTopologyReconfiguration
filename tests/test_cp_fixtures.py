"""Test Clopper-Pearson implementation with known values."""

import json
import tempfile
from pathlib import Path

from scripts.compute_cp import clopper_pearson_upper, compute_cp


def test_cp_formula_fixtures():
    """Verify CP upper bound matches expected values for known inputs."""

    # Test fixtures with expected values from our beta_inv approximation
    # Note: These use Wilson score approximation for small samples
    fixtures = [
        # (violations, total, expected_upper_bound)
        (0, 12, 0.2209),  # No violations in 12 trials
        (1, 12, 0.3849),  # 1 violation in 12 trials
        (3, 12, 0.5442),  # 3 violations in 12 trials
        (0, 100, 0.0295),  # No violations in 100 trials
        (5, 100, 0.0979),  # 5 violations in 100 trials
    ]

    for violations, total, expected in fixtures:
        actual = clopper_pearson_upper(violations, total)
        assert (
            abs(actual - expected) < 1e-3
        ), f"CP({violations}/{total}) = {actual:.4f}, expected {expected:.4f}"


def test_cp_zero_violations_special_case():
    """Test that zero violations is handled correctly."""

    # With 0 violations out of n trials, upper bound = 1 - (0.05)^(1/n)
    test_cases = [
        (10, 0.2589),  # 0/10 -> ~25.89%
        (20, 0.1392),  # 0/20 -> ~13.92%
        (50, 0.0580),  # 0/50 -> ~5.80%
        (100, 0.0295),  # 0/100 -> ~2.95%
    ]

    for n, expected in test_cases:
        actual = clopper_pearson_upper(0, n)
        assert abs(actual - expected) < 1e-3, f"CP(0/{n}) = {actual:.4f}, expected {expected:.4f}"


def test_cp_from_jsonl():
    """Test CP computation from JSONL data."""

    # Create test data with known violations
    data = [
        {"task_id": "task_1", "over_budget": False},
        {"task_id": "task_2", "over_budget": True},  # violation
        {"task_id": "task_3", "over_budget": False},
        {"task_id": "task_4", "over_budget": False},
        {"task_id": "task_5", "over_budget": True},  # violation
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
        assert result["violation_rate"] == 2 / 6

        # CP upper bound for 2/6 should be around 0.7276 (our approximation)
        assert abs(result["cp_upper_95"] - 0.7276) < 1e-3


def test_cp_respects_confidence_level():
    """Verify CP bound increases with confidence level."""

    # Same data, different confidence levels
    violations = 1
    total = 10

    cp_90 = clopper_pearson_upper(violations, total, confidence=0.90)
    cp_95 = clopper_pearson_upper(violations, total, confidence=0.95)
    cp_99 = clopper_pearson_upper(violations, total, confidence=0.99)

    # Higher confidence -> higher upper bound
    assert cp_90 < cp_95 < cp_99, f"Expected monotonic: {cp_90:.4f} < {cp_95:.4f} < {cp_99:.4f}"

    # Check approximate values (using our Wilson score approximation)
    assert abs(cp_90 - 0.3784) < 1e-3  # 1/10 at 90% confidence
    assert abs(cp_95 - 0.4400) < 1e-3  # 1/10 at 95% confidence
    assert abs(cp_99 - 0.5479) < 1e-3  # 1/10 at 99% confidence


def test_cp_large_n_edge_cases():
    """Test CP bound computation for large-n scenarios."""

    # Large-n with zero violations
    # Expected: 1 - (0.05)^(1/1000) ≈ 0.00299
    cp_large_zero = clopper_pearson_upper(0, 1000)
    expected_zero = 1.0 - (0.05 ** (1.0 / 1000))
    assert (
        abs(cp_large_zero - expected_zero) < 1e-5
    ), f"CP(0/1000) = {cp_large_zero:.5f}, expected {expected_zero:.5f}"
    assert (
        abs(cp_large_zero - 0.00299) < 1e-4
    ), f"CP(0/1000) should be ~0.00299, got {cp_large_zero:.5f}"

    # Near-boundary non-zero case (1 violation in 1000)
    # This should be very small but non-zero
    cp_large_one = clopper_pearson_upper(1, 1000)
    assert (
        cp_large_one > cp_large_zero
    ), f"CP(1/1000) = {cp_large_one:.5f} should be > CP(0/1000) = {cp_large_zero:.5f}"
    assert cp_large_one < 0.01, f"CP(1/1000) should be < 1%, got {cp_large_one:.5f}"
    # Expected value approximately 0.00432 (using our beta_inv approximation)
    assert (
        abs(cp_large_one - 0.00432) < 1e-3
    ), f"CP(1/1000) should be ~0.00432, got {cp_large_one:.5f}"

    # Verify monotonicity with increasing violations
    cp_2_1000 = clopper_pearson_upper(2, 1000)
    cp_5_1000 = clopper_pearson_upper(5, 1000)
    cp_10_1000 = clopper_pearson_upper(10, 1000)

    assert (
        cp_large_zero < cp_large_one < cp_2_1000 < cp_5_1000 < cp_10_1000
    ), "CP bounds should increase monotonically with violations"

    # Check that 10/1000 (1% empirical) has upper bound < 2%
    assert cp_10_1000 < 0.02, f"CP(10/1000) should be < 2%, got {cp_10_1000:.5f}"
