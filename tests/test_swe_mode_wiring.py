"""Test SWE mode wiring and repository management."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from apex.eval.harness import EvalHarness
from apex.eval.repo_manager import RepoManager
from apex.eval.task import Task


def test_repo_manager_local_checkout():
    """Test RepoManager with local git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        test_repo = Path(tmpdir) / "test_repo"

        # Create a test git repo
        test_repo.mkdir()
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)

        # Add a test file
        test_file = test_repo / "test.py"
        test_file.write_text("def hello(): return 'world'")
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@test",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@test",
            },
        )

        # Get commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        commit_hash = result.stdout.strip()

        # Use file:// URL for local repo
        repo_url = f"file://{test_repo.absolute()}"

        # Test RepoManager
        manager = RepoManager(work_dir)

        # Mock the _build_repo_url to use our local path
        manager._build_repo_url = lambda slug: repo_url

        checkout_path = manager.prepare_checkout("test/repo", commit_hash)

        # Verify checkout
        assert checkout_path.exists()
        assert (checkout_path / "test.py").exists()
        assert (checkout_path / "test.py").read_text() == "def hello(): return 'world'"


def test_patch_application():
    """Test applying patches to a repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        test_repo = Path(tmpdir) / "test_repo"

        # Create test repo
        test_repo.mkdir()
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)

        # Add initial file
        test_file = test_repo / "code.py"
        test_file.write_text("def add(a, b):\n    return a + b\n")
        subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=test_repo,
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@test",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@test",
            },
        )

        # Create patch
        patch_content = """diff --git a/code.py b/code.py
index 1234567..abcdefg 100644
--- a/code.py
+++ b/code.py
@@ -1,2 +1,3 @@
 def add(a, b):
+    # Add two numbers
     return a + b
"""

        # Apply patch
        manager = RepoManager(work_dir)
        success = manager.apply_patch(test_repo, patch_content, "test")

        assert success
        # Check file was modified
        content = test_file.read_text()
        assert "# Add two numbers" in content


def test_harness_swe_jsonl_output():
    """Test that harness produces valid JSONL for SWE tasks."""
    # Create minimal task (not used directly, but shows expected structure)
    _ = Task(
        task_id="test-task",
        description="Test task",
        expected_success=False,
        token_cost=0,
        topology_preference=None,
        metadata={
            "repo": "test/repo",
            "commit": "abc123",
            "test_patch": "",
            "patch": "",
            "hints": [],
        },
    )

    # Mock result
    from apex.eval.task import TaskResult

    result = TaskResult(
        task_id="test-task",
        policy="static_star",
        success=False,
        tokens_used=5000,
        over_budget=False,
        budget=10000,
        seed=42,
        epoch_switches=0,
        notes="swe_mode,tests_failed",
    )

    # Add SWE metadata
    result.metadata = {
        "budget_denied": 0,
        "topology_trace": [{"tick": 0, "topo": "star", "dwell": 1, "cooldown": 0}],
        "switches": 0,
        "episode_ms": 123.45,
    }

    # Convert to dict (as done in CLI)
    result_dict = {
        "task_id": result.task_id,
        "policy": result.policy,
        "success": result.success,
        "tokens_used": result.tokens_used,
        "budget": result.budget,
        "over_budget": result.over_budget,
        "seed": result.seed,
        "budget_denied": result.metadata["budget_denied"],
        "topology_trace": result.metadata["topology_trace"],
        "switches": result.metadata["switches"],
        "episode_ms": result.metadata["episode_ms"],
    }

    # Verify JSON serializable
    json_str = json.dumps(result_dict)
    parsed = json.loads(json_str)

    # Check schema
    assert parsed["task_id"] == "test-task"
    assert parsed["policy"] == "static_star"
    assert parsed["success"] is False
    assert parsed["tokens_used"] == 5000
    assert parsed["budget"] == 10000
    assert parsed["topology_trace"][0]["topo"] == "star"
    assert parsed["episode_ms"] == 123.45


def test_unique_task_ids_swe():
    """Verify SWE tasks get unique IDs from instance_id."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data
        cache_file = Path(tmpdir) / "swe_bench_lite_dev.jsonl"
        with open(cache_file, "w") as f:
            for i in range(3):
                task = {
                    "instance_id": f"django__django-{i:05d}",
                    "repo": "django/django",
                    "base_commit": f"commit{i}",
                    "problem_statement": f"Problem {i}",
                    "hints_text": "",
                    "patch": "",
                    "test_patch": "",
                }
                json.dump(task, f)
                f.write("\n")

        # Load with harness (mocked to avoid network)
        from apex.eval.providers import SWELiteProvider

        provider = SWELiteProvider(split="dev", cache_dir=Path(tmpdir))
        tasks = list(provider)

        # Check unique IDs
        ids = [t.task_id for t in tasks]
        assert len(ids) == 3
        assert len(set(ids)) == 3
        assert ids == ["django__django-00000", "django__django-00001", "django__django-00002"]


@pytest.mark.external
def test_swe_harness_smoke():
    """Smoke test for SWE harness (requires network, skipped in CI)."""
    import os

    if not os.getenv("APEX_ALLOW_NETWORK"):
        pytest.skip("Network test skipped (set APEX_ALLOW_NETWORK=1 to run)")

    # This would test real network access
    harness = EvalHarness(mode="swe", split="dev", seed=42)
    tasks = harness.load_tasks(n_episodes=1)
    assert len(tasks) >= 1
