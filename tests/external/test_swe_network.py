"""External tests that require network access.

Run with: APEX_ALLOW_NETWORK=1 pytest tests/external/test_swe_network.py
"""

from __future__ import annotations

import os

import pytest

from apex.eval.harness import EvalHarness
from apex.eval.providers.swe_lite import SWELiteProvider


@pytest.mark.skipif(
    os.getenv("APEX_ALLOW_NETWORK") != "1",
    reason="Network tests require APEX_ALLOW_NETWORK=1",
)
class TestSWENetworkAccess:
    """Tests that require network access to Hugging Face."""

    def test_download_swe_lite_dev(self):
        """Test downloading SWE-bench Lite dev split from HF."""
        provider = SWELiteProvider()

        # Download dev split (23 tasks)
        records = provider.load(split="dev", limit=2, offline=False)

        assert len(records) == 2
        # Verify real dataset fields
        assert all(r.task_id for r in records)
        assert all(r.repo for r in records)
        assert all(r.base_commit for r in records)
        assert all(r.problem_statement for r in records)

        # Check specific known tasks
        task_ids = [r.task_id for r in records]
        # Should be real task IDs from SWE-bench Lite
        assert all("__" in tid for tid in task_ids)  # Format: repo__issue

    def test_harness_load_real_tasks(self):
        """Test harness can load real SWE-bench tasks."""
        harness = EvalHarness(mode="swe", limit=3, offline=False)

        tasks = harness.load_tasks()

        assert len(tasks) == 3
        assert all(t.task_id for t in tasks)
        assert all("swe_record" in t.metadata for t in tasks)
        assert all(t.metadata["repo"] for t in tasks)

    def test_cache_persistence(self):
        """Test that downloaded data is cached."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            provider = SWELiteProvider(cache_dir=str(cache_dir))

            # First load - downloads from network
            records1 = provider.load(split="dev", limit=2, offline=False)

            # Check cache file was created
            cache_file = cache_dir / "swe_bench_lite_dev.jsonl"
            assert cache_file.exists()

            # Second load - should use cache
            provider2 = SWELiteProvider(cache_dir=str(cache_dir))
            records2 = provider2.load(split="dev", limit=2, offline=True)

            # Should get same data
            assert len(records1) == len(records2)
            assert records1[0].task_id == records2[0].task_id


@pytest.mark.skipif(
    os.getenv("APEX_ALLOW_NETWORK") != "1",
    reason="Network tests require APEX_ALLOW_NETWORK=1",
)
class TestOracleSmoke:
    """Test oracle smoke mode with real repos."""

    @pytest.mark.slow
    def test_oracle_smoke_real_task(self):
        """Test oracle smoke with a real SWE-bench task.

        This test is slow as it clones a real repository.
        """
        harness = EvalHarness(mode="swe", split="dev", limit=1, offline=False, oracle_smoke=True)

        tasks = harness.load_tasks()
        assert len(tasks) == 1

        # Run with oracle mode - should apply gold patch
        result = harness.run_episode(task=tasks[0], policy="static_star", budget=50000)

        # With oracle mode and gold patch, tests should pass
        # (assuming the task has a valid gold patch)
        assert result is not None
        assert result.task_id == tasks[0].task_id

        # Clean up
        harness.cleanup()
