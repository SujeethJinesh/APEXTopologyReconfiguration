#!/usr/bin/env python3
"""Test that SWE task list has 300 unique tasks and matches all result files."""

import json
from pathlib import Path


def test_task_list_has_300_unique_tasks():
    """Assert task list has exactly 300 unique task IDs."""
    task_list_path = Path("docs/A5/artifacts/swe/test/task_list_test300.jsonl")

    if not task_list_path.exists():
        # Skip test if artifacts don't exist (CI without artifacts)
        import pytest

        pytest.skip("Task list file not found (expected in full run)")

    task_ids = set()
    with open(task_list_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            if "__meta__" in obj:
                continue
            task_ids.add(obj["task_id"])

    assert len(task_ids) == 300, f"Expected 300 unique tasks, got {len(task_ids)}"


def test_all_result_files_match_task_list():
    """Assert all 5 result files have the same 300 task IDs as the task list."""
    base_path = Path("docs/A5/artifacts/swe/test")

    task_list_path = base_path / "task_list_test300.jsonl"
    result_files = [
        base_path / "static_star_test300.jsonl",
        base_path / "static_chain_test300.jsonl",
        base_path / "static_flat_test300.jsonl",
        base_path / "static_best_test300.jsonl",
        base_path / "apex_dynamic_test300.jsonl",
    ]

    # Check if files exist (skip in CI without artifacts)
    if not task_list_path.exists():
        import pytest

        pytest.skip("Artifact files not found (expected in full run)")

    # Load task list IDs
    expected_ids = set()
    with open(task_list_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            if "__meta__" in obj:
                continue
            expected_ids.add(obj["task_id"])

    assert len(expected_ids) == 300, f"Task list should have 300 tasks, got {len(expected_ids)}"

    # Check each result file
    for result_file in result_files:
        if not result_file.exists():
            continue  # Skip missing files

        result_ids = set()
        with open(result_file, "r") as f:
            for line in f:
                obj = json.loads(line)
                if "__meta__" in obj:
                    continue
                result_ids.add(obj["task_id"])

        assert (
            len(result_ids) == 300
        ), f"{result_file.name} should have 300 tasks, got {len(result_ids)}"
        assert result_ids == expected_ids, f"{result_file.name} task IDs don't match task list"


def test_metadata_present_in_all_files():
    """Assert all result files have __meta__ records with proper fields."""
    base_path = Path("docs/A5/artifacts/swe/test")

    result_files = [
        base_path / "static_star_test300.jsonl",
        base_path / "static_chain_test300.jsonl",
        base_path / "static_flat_test300.jsonl",
        base_path / "static_best_test300.jsonl",
        base_path / "apex_dynamic_test300.jsonl",
    ]

    for result_file in result_files:
        if not result_file.exists():
            import pytest

            pytest.skip(f"{result_file.name} not found (expected in full run)")

        # Check first line for metadata
        with open(result_file, "r") as f:
            first_line = f.readline()
            obj = json.loads(first_line)

            assert "__meta__" in obj, f"{result_file.name} missing __meta__ record"
            meta = obj["__meta__"]

            # Check required metadata fields
            assert "source" in meta, f"{result_file.name} metadata missing 'source'"

            # Derived files (like static_best) may not have dataset info directly
            if meta.get("source") != "derived":
                assert (
                    "dataset" in meta or "dataset_namespace" in meta
                ), f"{result_file.name} metadata missing dataset info"
