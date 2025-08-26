"""Repository manager for SWE-bench evaluation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional


class RepoManager:
    """Manages git repository operations for SWE-bench evaluation."""

    @staticmethod
    def prepare_workspace(
        record,
        work_root: str,
        oracle: bool = False,
        gh_token: Optional[str] = None,
    ) -> Path:
        """Prepare a workspace with repository at specified commit.

        Args:
            record: SWERecord with repo, base_commit, test_patch, patch
            work_root: Root directory for workspace
            oracle: If True, apply both test_patch and gold patch
            gh_token: Optional GitHub token for authentication

        Returns:
            Path to the prepared repository

        Raises:
            RuntimeError: If network is disabled or clone fails
        """
        # Check network permission
        if os.getenv("APEX_ALLOW_NETWORK") != "1":
            raise RuntimeError(
                "Network access is disabled. Set APEX_ALLOW_NETWORK=1 to clone repositories."
            )

        work_root = Path(work_root)
        work_root.mkdir(parents=True, exist_ok=True)

        # Create cache key from repo and commit
        repo_slug = record.repo.replace("/", "_")
        cache_key = f"{repo_slug}_{record.base_commit[:8]}"
        repo_path = work_root / cache_key

        # If already cached, reset and reuse
        if repo_path.exists() and (repo_path / ".git").exists():
            # Reset to clean state
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "clean", "-xdf"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
        else:
            # Clone repository
            repo_url = f"https://github.com/{record.repo}.git"
            if gh_token:
                # Use authenticated URL for higher rate limits
                repo_url = f"https://{gh_token}@github.com/{record.repo}.git"

            # Clone with minimal depth first
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to clone repository: {result.stderr}")

            # Fetch the specific commit if needed
            subprocess.run(
                ["git", "fetch", "--unshallow"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "fetch", "--all", "--tags"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )

        # Checkout the base commit
        result = subprocess.run(
            ["git", "checkout", record.base_commit],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to checkout commit: {result.stderr}")

        # Apply test patch
        if record.test_patch:
            success = RepoManager.apply_patch(repo_path, record.test_patch)
            if not success:
                raise RuntimeError("Failed to apply test patch")

        # Apply gold patch if oracle mode
        if oracle and record.patch:
            success = RepoManager.apply_patch(repo_path, record.patch)
            if not success:
                raise RuntimeError("Failed to apply gold patch in oracle mode")

        return repo_path

    @staticmethod
    def apply_patch(repo_path: Path, patch_str: str) -> bool:
        """Apply a patch to a repository.

        Args:
            repo_path: Path to repository
            patch_str: Patch content in unified diff format

        Returns:
            True if patch applied successfully, False otherwise
        """
        if not patch_str or not patch_str.strip():
            return True  # Empty patch is considered success

        # Write patch to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write(patch_str)
            patch_file = f.name

        try:
            # Try with -p0 first (most common for git diffs)
            result = subprocess.run(
                ["git", "apply", "--reject", "--whitespace=nowarn", "-p0", patch_file],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True

            # Fallback to -p1 if -p0 failed
            # First reset any partial application
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "clean", "-xdf"],
                cwd=repo_path,
                capture_output=True,
                check=False,
            )

            # Try with -p1
            result = subprocess.run(
                ["git", "apply", "--reject", "--whitespace=nowarn", "-p1", patch_file],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True

            # Log failure
            print(f"Patch application failed: {result.stderr[:500]}")
            return False

        finally:
            # Clean up temp file
            if os.path.exists(patch_file):
                os.unlink(patch_file)

    @staticmethod
    def run_tests(
        repo_path: Path,
        test_select: Optional[list[str]] = None,
        timeout_s: int = 180,
    ) -> dict:
        """Run tests in a repository.

        Args:
            repo_path: Path to repository
            test_select: Optional list of specific tests to run
            timeout_s: Timeout in seconds

        Returns:
            Dictionary with test results:
            - passed: number of passed tests
            - failed: number of failed tests
            - exit_code: pytest exit code
            - duration_s: execution time in seconds
        """
        start_time = time.time()

        # Build pytest command
        cmd = ["pytest", "-q"]

        # If specific tests selected, use -k to filter
        if test_select and len(test_select) > 0:
            # Handle long test lists
            test_expr = " or ".join(test_select)
            if len(test_expr) > 8192:
                # Too long for -k, run without filter (slower)
                print(f"Warning: Test list too long for -k, running all tests")
            else:
                cmd.extend(["-k", test_expr])

        # Add options for quick failure
        cmd.extend(["-x", "--maxfail=1"])

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )

            output = result.stdout + "\n" + result.stderr
            exit_code = result.returncode

        except subprocess.TimeoutExpired:
            duration_s = time.time() - start_time
            return {
                "passed": 0,
                "failed": 999,  # Large number to indicate timeout
                "exit_code": 124,  # Standard timeout exit code
                "duration_s": duration_s,
            }

        duration_s = time.time() - start_time

        # Parse test results from output
        passed = 0
        failed = 0

        # Look for pytest summary line
        import re

        for line in output.splitlines():
            line = line.strip()
            # Match patterns like "== 12 passed, 1 failed =="
            for match in re.finditer(r"(\d+)\s+(passed|failed|xfailed|xpassed)", line):
                count, status = int(match.group(1)), match.group(2)
                if status == "passed":
                    passed += count
                elif status == "failed":
                    failed += count
                # xfailed/xpassed are not counted as failures/passes for our purposes

        # If no summary found but exit code is 0, assume all passed
        if passed == 0 and failed == 0:
            if exit_code == 0:
                passed = 1  # At least one test passed
            else:
                failed = 1  # At least one test failed

        return {
            "passed": passed,
            "failed": failed,
            "exit_code": exit_code,
            "duration_s": duration_s,
        }

    @staticmethod
    def cleanup_workspace(work_root: str):
        """Clean up workspace directory.

        Args:
            work_root: Root directory to clean up
        """
        work_root = Path(work_root)
        if work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)