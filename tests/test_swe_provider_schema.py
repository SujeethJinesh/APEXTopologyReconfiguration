"""Test SWE-bench Lite provider schema and field mapping."""

import json
from pathlib import Path

from apex.eval.providers import SWELiteProvider


def test_load_local_fixture():
    """Test loading from local JSONL fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "swe_lite_min.jsonl"
    cache_dir = fixture_path.parent

    # Load provider with local fixture
    provider = SWELiteProvider(split="dev", cache_dir=cache_dir, limit=2)

    # Should load 2 tasks
    tasks = list(provider)
    assert len(tasks) == 2

    # Check first task fields
    task1 = tasks[0]
    assert task1.task_id == "test-001"
    assert task1.repo == "test/repo"
    assert task1.base_commit == "abc123"
    assert task1.problem == "Fix the bug in function foo"
    assert task1.hints == ["Check line 42"]
    assert "def foo()" in task1.patch
    assert "test_foo.py" in task1.test_patch


def test_field_mapping_correctness():
    """Test that fields map correctly from SWE-bench schema."""
    # Create test data matching SWE-bench schema
    test_data = {
        "instance_id": "django__django-12345",
        "repo": "django/django",
        "base_commit": "a1b2c3d4",
        "problem_statement": "Fix issue with QuerySet",
        "hints_text": "Look at models.py\nCheck line 100",
        "patch": "diff content here",
        "test_patch": "test diff content",
    }

    # Write to temp file
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "swe_bench_lite_dev.jsonl"
        with open(cache_file, "w") as f:
            json.dump(test_data, f)
            f.write("\n")

        # Load with provider
        provider = SWELiteProvider(split="dev", cache_dir=Path(tmpdir))
        tasks = list(provider)

        assert len(tasks) == 1
        task = tasks[0]

        # Verify field mapping
        assert task.task_id == test_data["instance_id"]
        assert task.repo == test_data["repo"]
        assert task.base_commit == test_data["base_commit"]
        assert task.problem == test_data["problem_statement"]
        assert task.hints == ["Look at models.py", "Check line 100"]
        assert task.patch == test_data["patch"]
        assert task.test_patch == test_data["test_patch"]


def test_no_global_rng_mutation():
    """Verify provider doesn't mutate global RNG state."""
    import random

    # Save global RNG state
    state_before = random.getstate()

    # Load provider
    fixture_path = Path(__file__).parent / "fixtures" / "swe_lite_min.jsonl"
    provider = SWELiteProvider(split="dev", cache_dir=fixture_path.parent, limit=2)

    # Iterate through tasks
    tasks = list(provider)
    assert len(tasks) == 2

    # Check global RNG unchanged
    state_after = random.getstate()
    assert state_before == state_after, "Provider must not mutate global RNG"


def test_empty_hints_handling():
    """Test handling of empty hints field."""
    test_data = {
        "instance_id": "test-empty-hints",
        "repo": "test/repo",
        "base_commit": "abc",
        "problem_statement": "Test problem",
        "hints_text": "",  # Empty hints
        "patch": "patch",
        "test_patch": "test",
    }

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "swe_bench_lite_dev.jsonl"
        with open(cache_file, "w") as f:
            json.dump(test_data, f)
            f.write("\n")

        provider = SWELiteProvider(split="dev", cache_dir=Path(tmpdir))
        tasks = list(provider)

        assert len(tasks) == 1
        assert tasks[0].hints == []  # Empty list for empty hints


def test_limit_parameter():
    """Test that limit parameter correctly restricts number of tasks."""
    # Create multiple tasks
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "swe_bench_lite_dev.jsonl"
        with open(cache_file, "w") as f:
            for i in range(10):
                task = {
                    "instance_id": f"test-{i:03d}",
                    "repo": f"repo/{i}",
                    "base_commit": f"commit{i}",
                    "problem_statement": f"Problem {i}",
                    "hints_text": "",
                    "patch": f"patch {i}",
                    "test_patch": f"test {i}",
                }
                json.dump(task, f)
                f.write("\n")

        # Load with limit
        provider = SWELiteProvider(split="dev", cache_dir=Path(tmpdir), limit=5)
        tasks = list(provider)

        assert len(tasks) == 5
        assert tasks[0].task_id == "test-000"
        assert tasks[4].task_id == "test-004"
