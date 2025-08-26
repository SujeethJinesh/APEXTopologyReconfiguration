"""Test bootstrap lift computation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


class TestBootstrapLift:
    """Test paired bootstrap confidence intervals for lift."""

    def test_paired_sampling(self):
        """Test that bootstrap samples are paired by task."""
        # Create toy JSONLs
        apex_data = [
            {"task_id": "task_1", "success": True, "tokens_used": 100},
            {"task_id": "task_2", "success": True, "tokens_used": 200},
            {"task_id": "task_3", "success": False, "tokens_used": 300},
        ]

        static_data = [
            {"task_id": "task_1", "success": False, "tokens_used": 150},
            {"task_id": "task_2", "success": True, "tokens_used": 250},
            {"task_id": "task_3", "success": False, "tokens_used": 350},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write test data
            apex_path = Path(tmpdir) / "apex.jsonl"
            static_path = Path(tmpdir) / "static.jsonl"
            output_path = Path(tmpdir) / "lift.json"

            with open(apex_path, "w") as f:
                for item in apex_data:
                    json.dump(item, f)
                    f.write("\n")

            with open(static_path, "w") as f:
                for item in static_data:
                    json.dump(item, f)
                    f.write("\n")

            # Run compute_lift
            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_lift",
                    "--a",
                    str(apex_path),
                    "--b",
                    str(static_path),
                    "--out",
                    str(output_path),
                    "--paired",
                    "--n-bootstrap",
                    "100",
                    "--seed",
                    "42",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"compute_lift failed: {result.stderr}"

            # Load and verify output
            with open(output_path, "r") as f:
                lift_result = json.load(f)

            # Check structure
            assert "lift_abs" in lift_result
            assert "ci_low" in lift_result
            assert "ci_high" in lift_result
            assert "n" in lift_result
            assert "seed" in lift_result

            # Verify lift calculation
            # APEX: 2/3 success, Static: 1/3 success
            # Lift = 2/3 - 1/3 = 1/3 ≈ 0.333
            assert abs(lift_result["lift_abs"] - 0.333) < 0.01

            # CI should contain the true value
            assert lift_result["ci_low"] <= lift_result["lift_abs"]
            assert lift_result["ci_high"] >= lift_result["lift_abs"]

            # Number of tasks should match
            assert lift_result["n"] == 3

    def test_no_common_tasks(self):
        """Test handling when no common tasks exist."""
        apex_data = [
            {"task_id": "task_A", "success": True, "tokens_used": 100},
        ]

        static_data = [
            {"task_id": "task_B", "success": False, "tokens_used": 150},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            apex_path = Path(tmpdir) / "apex.jsonl"
            static_path = Path(tmpdir) / "static.jsonl"
            output_path = Path(tmpdir) / "lift.json"

            with open(apex_path, "w") as f:
                json.dump(apex_data[0], f)
                f.write("\n")

            with open(static_path, "w") as f:
                json.dump(static_data[0], f)
                f.write("\n")

            # Should handle gracefully
            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.compute_lift",
                    "--a",
                    str(apex_path),
                    "--b",
                    str(static_path),
                    "--out",
                    str(output_path),
                    "--seed",
                    "42",
                ],
                capture_output=True,
                text=True,
            )

            # Should exit with error message
            assert "No common tasks" in result.stdout

    def test_deterministic_bootstrap(self):
        """Test that bootstrap is deterministic with seed."""
        apex_data = [
            {"task_id": f"task_{i}", "success": i % 2 == 0, "tokens_used": 100 * i}
            for i in range(10)
        ]

        static_data = [
            {"task_id": f"task_{i}", "success": i % 3 == 0, "tokens_used": 150 * i}
            for i in range(10)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            apex_path = Path(tmpdir) / "apex.jsonl"
            static_path = Path(tmpdir) / "static.jsonl"

            with open(apex_path, "w") as f:
                for item in apex_data:
                    json.dump(item, f)
                    f.write("\n")

            with open(static_path, "w") as f:
                for item in static_data:
                    json.dump(item, f)
                    f.write("\n")

            # Run twice with same seed
            results = []
            for run in range(2):
                output_path = Path(tmpdir) / f"lift_{run}.json"

                import subprocess

                result = subprocess.run(
                    [
                        "python3",
                        "-m",
                        "scripts.compute_lift",
                        "--a",
                        str(apex_path),
                        "--b",
                        str(static_path),
                        "--out",
                        str(output_path),
                        "--n-bootstrap",
                        "200",
                        "--seed",
                        "42",
                    ],
                    capture_output=True,
                    text=True,
                )

                assert result.returncode == 0

                with open(output_path, "r") as f:
                    results.append(json.load(f))

            # Results should be identical with same seed
            assert results[0]["lift_abs"] == results[1]["lift_abs"]
            assert results[0]["ci_low"] == results[1]["ci_low"]
            assert results[0]["ci_high"] == results[1]["ci_high"]
