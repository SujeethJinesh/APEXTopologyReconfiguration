"""Test repository manager functionality."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apex.eval.providers.swe_lite import SWERecord
from apex.eval.repo_manager import RepoManager


class TestRepoManager:
    """Test RepoManager functionality."""

    def test_apply_patch_empty(self):
        """Test applying empty patch succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            success = RepoManager.apply_patch(repo_path, "")
            assert success is True

            success = RepoManager.apply_patch(repo_path, "   \n  ")
            assert success is True

    @patch("subprocess.run")
    def test_apply_patch_p0_success(self, mock_run):
        """Test patch application with -p0 succeeds."""
        # Mock successful -p0 application
        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            patch_str = (
                "diff --git a/file.py b/file.py\n"
                "--- a/file.py\n"
                "+++ b/file.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new"
            )

            success = RepoManager.apply_patch(repo_path, patch_str)
            assert success is True

            # Verify git apply was called with -p0
            calls = mock_run.call_args_list
            assert len(calls) == 1
            assert "-p0" in calls[0][0][0]

    @patch("subprocess.run")
    def test_apply_patch_p1_fallback(self, mock_run):
        """Test patch falls back to -p1 when -p0 fails."""
        # Mock: -p0 fails, reset succeeds, clean succeeds, -p1 succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1),  # -p0 fails
            MagicMock(returncode=0),  # git reset
            MagicMock(returncode=0),  # git clean
            MagicMock(returncode=0),  # -p1 succeeds
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            patch_str = (
                "diff --git a/file.py b/file.py\n"
                "--- a/file.py\n"
                "+++ b/file.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new"
            )

            success = RepoManager.apply_patch(repo_path, patch_str)
            assert success is True

            # Verify fallback sequence
            calls = mock_run.call_args_list
            assert len(calls) == 4
            assert "-p0" in calls[0][0][0]
            assert "reset" in calls[1][0][0]
            assert "clean" in calls[2][0][0]
            assert "-p1" in calls[3][0][0]

    @patch("subprocess.run")
    def test_apply_patch_both_fail(self, mock_run):
        """Test patch returns False when both -p0 and -p1 fail."""
        # Mock: all attempts fail
        mock_run.return_value = MagicMock(returncode=1, stderr="patch failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            patch_str = (
                "diff --git a/file.py b/file.py\n"
                "--- a/file.py\n"
                "+++ b/file.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new"
            )

            success = RepoManager.apply_patch(repo_path, patch_str)
            assert success is False

    def test_prepare_workspace_network_gating(self):
        """Test network access is properly gated."""
        record = SWERecord(
            task_id="test",
            repo="test/repo",
            base_commit="abc123",
            env_setup_commit="def456",
            patch="",
            test_patch="",
            fail_to_pass=[],
            pass_to_pass=[],
            problem_statement="Test",
            hints_text="",
        )

        # Without APEX_ALLOW_NETWORK, should fail
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="Network access is disabled"):
                RepoManager.prepare_workspace(record, "/tmp/test")

        # With APEX_ALLOW_NETWORK=1, should attempt clone
        with patch.dict(os.environ, {"APEX_ALLOW_NETWORK": "1"}):
            with patch("subprocess.run") as mock_run:
                # Mock clone failure to avoid actual network
                mock_run.return_value = MagicMock(returncode=1, stderr="Connection refused")

                with pytest.raises(RuntimeError, match="Failed to clone"):
                    RepoManager.prepare_workspace(record, "/tmp/test")

    @patch("subprocess.run")
    def test_run_tests_parsing(self, mock_run):
        """Test test output parsing."""
        # Mock pytest output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="collected 5 items\n\n== 4 passed, 1 failed in 2.50s ==",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = RepoManager.run_tests(Path(tmpdir))

            assert result["passed"] == 4
            assert result["failed"] == 1
            assert result["exit_code"] == 0

    @patch("subprocess.run")
    def test_run_tests_timeout(self, mock_run):
        """Test handling of test timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 180)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = RepoManager.run_tests(Path(tmpdir), timeout_s=180)

            assert result["failed"] == 999  # Timeout indicator
            assert result["exit_code"] == 124
            assert result["passed"] == 0

    @patch("subprocess.run")
    def test_run_tests_with_selection(self, mock_run):
        """Test running specific tests with -k filter."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_select = ["test_one", "test_two", "test_three"]
            RepoManager.run_tests(Path(tmpdir), test_select=test_select)

            # Verify -k was used with OR expression
            call_args = mock_run.call_args[0][0]
            assert "-k" in call_args
            k_index = call_args.index("-k")
            assert call_args[k_index + 1] == "test_one or test_two or test_three"

    def test_cleanup_workspace(self):
        """Test workspace cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir) / "test_workspace"
            work_root.mkdir()
            test_file = work_root / "test.txt"
            test_file.write_text("test")

            assert work_root.exists()
            assert test_file.exists()

            RepoManager.cleanup_workspace(str(work_root))

            assert not work_root.exists()
            assert not test_file.exists()
