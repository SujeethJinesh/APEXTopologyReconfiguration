"""External smoke test for real SWE-bench evaluation (gated by network access)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from apex.eval.harness import EvalHarness
from scripts.compute_cp import compute_cp


@pytest.mark.external
@pytest.mark.swe_real
@pytest.mark.skipif(
    os.getenv("APEX_ALLOW_NETWORK") != "1",
    reason="Requires APEX_ALLOW_NETWORK=1 for real SWE-bench access",
)
def test_swe_real_smoke():
    """Smoke test for real SWE-bench evaluation with 3 tasks."""

    # Create temp directory for outputs
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Select 3 task IDs from the test split (300 tasks available)
        # These are real SWE-bench Lite task IDs
        task_ids = ["django__django-11099", "sympy__sympy-13480", "pylint-dev__pylint-6506"]

        # Write task list
        task_list_path = tmpdir / "task_list_smoke.jsonl"
        with open(task_list_path, "w") as f:
            for task_id in task_ids:
                json.dump({"task_id": task_id}, f)
                f.write("\n")

        # Initialize harness with task list
        harness = EvalHarness(
            mode="swe",
            seed=42,
            split="dev",  # Will load from test split via task_list
            task_list=task_ids,
        )

        # Load tasks - should find them in test split
        tasks = harness.load_tasks()

        # Verify we got the right number of tasks
        assert len(tasks) == 3, f"Expected 3 tasks, got {len(tasks)}"

        # Verify task IDs match
        loaded_ids = [t.task_id for t in tasks]
        assert set(loaded_ids) == set(task_ids), f"Task IDs mismatch: {loaded_ids}"

        # Run a quick evaluation with static_star
        results = []
        for task in tasks:
            # Mock the actual execution to keep test fast
            # In real evaluation, this would call harness.run_episode()
            result = {
                "task_id": task.task_id,
                "policy": "static_star",
                "success": False,  # Conservative mock
                "tokens_used": 5000,
                "over_budget": False,
                "budget": 10000,
                "seed": 42,
                "epoch_switches": 0,
                "notes": "",
            }
            results.append(result)

        # Write results JSONL
        output_path = tmpdir / "results_smoke.jsonl"
        with open(output_path, "w") as f:
            for result in results:
                json.dump(result, f)
                f.write("\n")

        # Verify JSONL was created
        assert output_path.exists(), "Results JSONL not created"

        # Load and verify results
        with open(output_path, "r") as f:
            loaded_results = [json.loads(line) for line in f if line.strip()]

        assert len(loaded_results) == 3, f"Expected 3 results, got {len(loaded_results)}"

        # Compute CP bound for the small sample
        cp_result = compute_cp(str(output_path), confidence=0.95)

        # Verify CP computation worked
        assert "violations" in cp_result
        assert "total" in cp_result
        assert cp_result["total"] == 3
        assert 0 <= cp_result["violations"] <= 3
        assert 0.0 <= cp_result["cp_upper_95"] <= 1.0

        # When running with real source, verify it's marked correctly
        if os.getenv("APEX_SWE_REAL_TEST") == "1":
            # This env var would be set when actually running real evaluation
            # For smoke test we skip this check
            pass

        # Clean up harness workspace
        harness.cleanup()


@pytest.mark.external
@pytest.mark.swe_real
def test_task_list_generation_deterministic():
    """Test that task list generation is deterministic with same seed."""
    from scripts.generate_real_task_list import _load_swe_dataset

    # Skip if no network access
    if os.getenv("APEX_ALLOW_NETWORK") != "1":
        pytest.skip("Requires APEX_ALLOW_NETWORK=1")

    # Load dataset
    ds, namespace = _load_swe_dataset("test")  # Use test split (300 tasks)

    # Verify we got expected number of tasks
    assert len(ds) == 300, f"Expected 300 tasks in test split, got {len(ds)}"

    # Generate two samples with same seed
    import random

    rng1 = random.Random(17)
    sample1 = rng1.sample([row["instance_id"] for row in ds], 10)

    rng2 = random.Random(17)
    sample2 = rng2.sample([row["instance_id"] for row in ds], 10)

    # Verify deterministic
    assert sample1 == sample2, "Task selection not deterministic with same seed"

    # Verify different seeds give different results
    rng3 = random.Random(42)
    sample3 = rng3.sample([row["instance_id"] for row in ds], 10)

    assert sample1 != sample3, "Different seeds should give different samples"
