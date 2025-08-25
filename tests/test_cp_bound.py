"""Test Clopper-Pearson confidence bound computation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestClopperPearson:
    """Test CP bound calculation."""

    def test_cp_formula(self):
        """Test CP upper bound matches formula."""
        # Test data with known violations
        test_data = [
            {"task_id": "task_1", "over_budget": False},
            {"task_id": "task_2", "over_budget": True},
            {"task_id": "task_3", "over_budget": False},
            {"task_id": "task_4", "over_budget": False},
            {"task_id": "task_5", "over_budget": True},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "episodes.jsonl"
            output_path = Path(tmpdir) / "cp.json"

            with open(input_path, "w") as f:
                for item in test_data:
                    json.dump(item, f)
                    f.write("\n")

            # Run compute_cp
            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_cp",
                    "--in",
                    str(input_path),
                    "--out",
                    str(output_path),
                    "--confidence",
                    "0.95",
                    "--seed",
                    "42",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"compute_cp failed: {result.stderr}"

            # Load result
            with open(output_path, "r") as f:
                cp_result = json.load(f)

            # Verify structure
            assert cp_result["violations"] == 2
            assert cp_result["total"] == 5
            assert "cp_upper_95" in cp_result
            assert cp_result["empirical_rate"] == pytest.approx(0.4, rel=1e-3)

            # CP bound should be > empirical rate
            assert cp_result["cp_upper_95"] > cp_result["empirical_rate"]

            # For 2/5 violations, CP upper should be around 0.65-0.75
            assert 0.6 < cp_result["cp_upper_95"] < 0.8

    def test_no_violations(self):
        """Test CP bound when no violations occur."""
        test_data = [{"task_id": f"task_{i}", "over_budget": False} for i in range(10)]

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "episodes.jsonl"
            output_path = Path(tmpdir) / "cp.json"

            with open(input_path, "w") as f:
                for item in test_data:
                    json.dump(item, f)
                    f.write("\n")

            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_cp",
                    "--in",
                    str(input_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            with open(output_path, "r") as f:
                cp_result = json.load(f)

            assert cp_result["violations"] == 0
            assert cp_result["total"] == 10
            assert cp_result["empirical_rate"] == 0.0

            # For 0 violations out of 10, upper bound should be small
            # Approximately 1 - (1 - 0.95)^(1/10) ≈ 0.26
            assert 0.2 < cp_result["cp_upper_95"] < 0.3

    def test_all_violations(self):
        """Test CP bound when all episodes violate."""
        test_data = [{"task_id": f"task_{i}", "over_budget": True} for i in range(5)]

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "episodes.jsonl"
            output_path = Path(tmpdir) / "cp.json"

            with open(input_path, "w") as f:
                for item in test_data:
                    json.dump(item, f)
                    f.write("\n")

            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_cp",
                    "--in",
                    str(input_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            with open(output_path, "r") as f:
                cp_result = json.load(f)

            assert cp_result["violations"] == 5
            assert cp_result["total"] == 5
            assert cp_result["empirical_rate"] == 1.0
            assert cp_result["cp_upper_95"] == 1.0

    def test_floating_tolerance(self):
        """Test that CP bound computation has appropriate floating tolerance."""
        # Create dataset with specific violation pattern
        n_total = 100
        n_violations = 5

        test_data = []
        for i in range(n_total):
            test_data.append({"task_id": f"task_{i}", "over_budget": i < n_violations})

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "episodes.jsonl"
            output_path = Path(tmpdir) / "cp.json"

            with open(input_path, "w") as f:
                for item in test_data:
                    json.dump(item, f)
                    f.write("\n")

            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_cp",
                    "--in",
                    str(input_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            with open(output_path, "r") as f:
                cp_result = json.load(f)

            # Empirical rate
            empirical = n_violations / n_total
            assert abs(cp_result["empirical_rate"] - empirical) < 1e-6

            # CP bound should be reasonable
            assert cp_result["cp_upper_95"] > empirical
            assert cp_result["cp_upper_95"] < 0.15  # Should be < 15% for 5/100
