"""Test harness with SWE mode."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from apex.eval.harness import EvalHarness
from apex.eval.providers.swe_lite import SWERecord


class TestHarnessSWEMode:
    """Test harness SWE mode functionality."""

    def test_swe_mode_network_gating(self):
        """Test SWE mode requires network permission."""
        # Without APEX_ALLOW_NETWORK, should fail
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="requires network access"):
                EvalHarness(mode="swe", offline=False)

        # With APEX_ALLOW_NETWORK=1, should succeed
        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe")
            assert harness.mode == "swe"

        # Offline mode should work without network
        with patch.dict(os.environ, {}, clear=True):
            harness = EvalHarness(mode="swe", offline=True)
            assert harness.mode == "swe"
            assert harness.offline is True

    def test_load_tasks_swe_mode(self):
        """Test loading tasks in SWE mode."""
        # Create mock SWE records
        mock_records = [
            SWERecord(
                task_id="task1",
                repo="repo1",
                base_commit="abc123",
                env_setup_commit="def456",
                patch="patch1",
                test_patch="test_patch1",
                fail_to_pass=["test1"],
                pass_to_pass=["test2"],
                problem_statement="Problem 1 " * 50,  # Long description
                hints_text="Hint 1",
            ),
            SWERecord(
                task_id="task2",
                repo="repo2",
                base_commit="ghi789",
                env_setup_commit="jkl012",
                patch="patch2",
                test_patch="test_patch2",
                fail_to_pass=["test3"],
                pass_to_pass=[],
                problem_statement="Problem 2",
                hints_text="Hint 2",
            ),
        ]

        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe")

            # Mock provider.load
            with patch.object(harness.provider, "load", return_value=mock_records):
                tasks = harness.load_tasks(n_episodes=2)

                assert len(tasks) == 2
                assert tasks[0].task_id == "task1"
                assert tasks[0].description[:10] == "Problem 1 "
                assert len(tasks[0].description) == 200  # Truncated
                assert tasks[0].metadata["repo"] == "repo1"
                assert tasks[0].metadata["swe_record"] == mock_records[0]

                assert tasks[1].task_id == "task2"
                assert tasks[1].metadata["repo"] == "repo2"

    @patch("apex.eval.harness.RepoManager")
    def test_run_episode_swe_mode(self, mock_repo_manager):
        """Test running episode in SWE mode."""
        # Mock RepoManager methods
        mock_repo_manager.prepare_workspace.return_value = Path("/tmp/test_repo")
        mock_repo_manager.run_tests.return_value = {
            "passed": 5,
            "failed": 0,
            "exit_code": 0,
            "duration_s": 3.5,
        }

        # Create SWE task
        swe_record = SWERecord(
            task_id="test_task",
            repo="test/repo",
            base_commit="abc123",
            env_setup_commit="def456",
            patch="patch",
            test_patch="test_patch",
            fail_to_pass=["test1", "test2"],
            pass_to_pass=["test3"],
            problem_statement="Test problem",
            hints_text="Test hint",
        )

        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe", oracle_smoke=False)

            # Create task with SWE metadata
            from apex.eval.task import Task

            task = Task(
                task_id="test_task",
                description="Test",
                expected_success=None,
                token_cost=0,
                topology_preference="star",
                metadata={"swe_record": swe_record},
            )

            # Run episode
            result = harness.run_episode(task=task, policy="static_star", budget=10000)

            # Verify RepoManager was called correctly
            mock_repo_manager.prepare_workspace.assert_called_once()
            call_args = mock_repo_manager.prepare_workspace.call_args
            assert call_args[1]["record"] == swe_record
            assert call_args[1]["oracle"] is False

            mock_repo_manager.run_tests.assert_called_once()
            call_args = mock_repo_manager.run_tests.call_args
            assert call_args[1]["test_select"] == ["test1", "test2"]

            # Check result
            assert result.success is True  # Tests passed
            assert result.tokens_used == 1350  # 3.5 * 100 + 1000
            assert result.over_budget is False
            assert "mode=swe" in result.notes

    @patch("apex.eval.harness.RepoManager")
    def test_run_episode_oracle_smoke(self, mock_repo_manager):
        """Test oracle smoke mode applies gold patch."""
        mock_repo_manager.prepare_workspace.return_value = Path("/tmp/test_repo")
        mock_repo_manager.run_tests.return_value = {
            "passed": 2,
            "failed": 0,
            "exit_code": 0,
            "duration_s": 2.0,
        }

        swe_record = SWERecord(
            task_id="oracle_test",
            repo="test/repo",
            base_commit="abc123",
            env_setup_commit="def456",
            patch="gold_patch",
            test_patch="test_patch",
            fail_to_pass=["test1"],
            pass_to_pass=["test2"],
            problem_statement="Oracle test",
            hints_text="",
        )

        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe", oracle_smoke=True)

            from apex.eval.task import Task

            task = Task(
                task_id="oracle_test",
                description="Oracle",
                expected_success=None,
                token_cost=0,
                topology_preference="star",
                metadata={"swe_record": swe_record},
            )

            result = harness.run_episode(task=task, policy="static_star", budget=5000)

            # Verify oracle=True was passed
            call_args = mock_repo_manager.prepare_workspace.call_args
            assert call_args[1]["oracle"] is True

            assert result.success is True
            assert result.tokens_used == 1200  # 2.0 * 100 + 1000

    @patch("apex.eval.harness.RepoManager")
    def test_run_episode_test_failure(self, mock_repo_manager):
        """Test handling test failures."""
        mock_repo_manager.prepare_workspace.return_value = Path("/tmp/test_repo")
        mock_repo_manager.run_tests.return_value = {
            "passed": 2,
            "failed": 3,
            "exit_code": 1,
            "duration_s": 4.0,
        }

        swe_record = SWERecord(
            task_id="fail_test",
            repo="test/repo",
            base_commit="abc123",
            env_setup_commit="def456",
            patch="",
            test_patch="",
            fail_to_pass=["test1"],
            pass_to_pass=[],
            problem_statement="Fail test",
            hints_text="",
        )

        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe")

            from apex.eval.task import Task

            task = Task(
                task_id="fail_test",
                description="Fail",
                expected_success=None,
                token_cost=0,
                topology_preference="star",
                metadata={"swe_record": swe_record},
            )

            result = harness.run_episode(task=task, policy="static_star", budget=10000)

            # Task should fail due to test failures
            assert result.success is False
            assert result.tokens_used == 1400  # 4.0 * 100 + 1000

    def test_cleanup(self):
        """Test workspace cleanup."""
        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            harness = EvalHarness(mode="swe")

            # Create actual temp directory
            harness.work_root.mkdir(exist_ok=True)
            test_file = harness.work_root / "test.txt"
            test_file.write_text("test")

            assert harness.work_root.exists()

            with patch("apex.eval.harness.RepoManager.cleanup_workspace") as mock_cleanup:
                harness.cleanup()
                mock_cleanup.assert_called_once_with(str(harness.work_root))
