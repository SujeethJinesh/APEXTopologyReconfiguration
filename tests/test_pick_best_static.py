"""Test best static policy selection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


class TestPickBestStatic:
    """Test best static policy selection logic."""

    def test_best_selection_no_apex_leak(self):
        """Ensure best static is chosen only from static policies."""
        # Create test data with different policies
        star_data = [
            {"task_id": "task_1", "policy": "static_star", "success": True, "tokens_used": 100},
            {"task_id": "task_2", "policy": "static_star", "success": False, "tokens_used": 200},
        ]

        chain_data = [
            {"task_id": "task_1", "policy": "static_chain", "success": False, "tokens_used": 90},
            {"task_id": "task_2", "policy": "static_chain", "success": True, "tokens_used": 180},
        ]

        flat_data = [
            {"task_id": "task_1", "policy": "static_flat", "success": True, "tokens_used": 110},
            {"task_id": "task_2", "policy": "static_flat", "success": True, "tokens_used": 190},
        ]

        # Note: APEX data would NOT be selected even if present
        # This test verifies that only static policies are considered

        with tempfile.TemporaryDirectory() as tmpdir:
            star_path = Path(tmpdir) / "star.jsonl"
            chain_path = Path(tmpdir) / "chain.jsonl"
            flat_path = Path(tmpdir) / "flat.jsonl"
            output_path = Path(tmpdir) / "best.jsonl"

            # Write static policies
            paths_data = [(star_path, star_data), (chain_path, chain_data), (flat_path, flat_data)]
            for path, data in paths_data:
                with open(path, "w") as f:
                    for item in data:
                        json.dump(item, f)
                        f.write("\n")

            # Run pick_best_static
            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.pick_best_static",
                    "--star",
                    str(star_path),
                    "--chain",
                    str(chain_path),
                    "--flat",
                    str(flat_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"pick_best_static failed: {result.stderr}"

            # Load and verify output
            best_results = []
            with open(output_path, "r") as f:
                for line in f:
                    if line.strip():
                        best_results.append(json.loads(line))

            # Should have 2 tasks
            assert len(best_results) == 2

            # Check task_1: chain has lowest tokens (90) but fails, star succeeds with 100
            task_1 = [r for r in best_results if r["task_id"] == "task_1"][0]
            assert task_1["original_policy"] == "static_star"  # Successful with lowest tokens
            assert task_1["policy"] == "static_best"
            assert task_1["tokens_used"] == 100

            # Check task_2: chain succeeds with 180, flat succeeds with 190, star fails
            task_2 = [r for r in best_results if r["task_id"] == "task_2"][0]
            assert task_2["original_policy"] == "static_chain"  # Successful with lowest tokens
            assert task_2["policy"] == "static_best"
            assert task_2["tokens_used"] == 180

            # Verify NO apex results leaked in
            for result in best_results:
                assert "bandit" not in result.get("original_policy", "")
                assert result["policy"] == "static_best"

    def test_all_fail_case(self):
        """Test selection when all static policies fail a task."""
        star_data = [
            {
                "task_id": "hard_task",
                "policy": "static_star",
                "success": False,
                "tokens_used": 1000,
            },
        ]

        chain_data = [
            {
                "task_id": "hard_task",
                "policy": "static_chain",
                "success": False,
                "tokens_used": 900,
            },
        ]

        flat_data = [
            {"task_id": "hard_task", "policy": "static_flat", "success": False, "tokens_used": 950},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            star_path = Path(tmpdir) / "star.jsonl"
            chain_path = Path(tmpdir) / "chain.jsonl"
            flat_path = Path(tmpdir) / "flat.jsonl"
            output_path = Path(tmpdir) / "best.jsonl"

            paths_data = [(star_path, star_data), (chain_path, chain_data), (flat_path, flat_data)]
            for path, data in paths_data:
                with open(path, "w") as f:
                    json.dump(data[0], f)
                    f.write("\n")

            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.pick_best_static",
                    "--star",
                    str(star_path),
                    "--chain",
                    str(chain_path),
                    "--flat",
                    str(flat_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            with open(output_path, "r") as f:
                best_result = json.loads(f.readline())

            # Should pick chain (lowest tokens when all fail)
            assert best_result["original_policy"] == "static_chain"
            assert best_result["tokens_used"] == 900
            assert best_result["success"] is False

    def test_missing_task_handling(self):
        """Test handling when a task is missing from some policies."""
        star_data = [
            {"task_id": "task_1", "policy": "static_star", "success": True, "tokens_used": 100},
            {"task_id": "task_2", "policy": "static_star", "success": True, "tokens_used": 200},
        ]

        # Chain missing task_2
        chain_data = [
            {"task_id": "task_1", "policy": "static_chain", "success": True, "tokens_used": 110},
        ]

        flat_data = [
            {"task_id": "task_1", "policy": "static_flat", "success": True, "tokens_used": 120},
            {"task_id": "task_2", "policy": "static_flat", "success": False, "tokens_used": 210},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            star_path = Path(tmpdir) / "star.jsonl"
            chain_path = Path(tmpdir) / "chain.jsonl"
            flat_path = Path(tmpdir) / "flat.jsonl"
            output_path = Path(tmpdir) / "best.jsonl"

            paths_data = [(star_path, star_data), (chain_path, chain_data), (flat_path, flat_data)]
            for path, data in paths_data:
                with open(path, "w") as f:
                    for item in data:
                        json.dump(item, f)
                        f.write("\n")

            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.pick_best_static",
                    "--star",
                    str(star_path),
                    "--chain",
                    str(chain_path),
                    "--flat",
                    str(flat_path),
                    "--out",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            best_results = []
            with open(output_path, "r") as f:
                for line in f:
                    if line.strip():
                        best_results.append(json.loads(line))

            # Should handle both tasks
            assert len(best_results) == 2

            # Task 1: star has lowest (100)
            task_1 = [r for r in best_results if r["task_id"] == "task_1"][0]
            assert task_1["original_policy"] == "static_star"

            # Task 2: only star succeeds
            task_2 = [r for r in best_results if r["task_id"] == "task_2"][0]
            assert task_2["original_policy"] == "static_star"
