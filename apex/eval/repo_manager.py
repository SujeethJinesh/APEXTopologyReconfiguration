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

        # Environment bootstrap
        env_status = RepoManager.bootstrap_environment(repo_path)
        if not env_status["success"]:
            print(
                f"Warning: Environment bootstrap failed for {record.task_id}: "
                f"{env_status.get('error', 'Unknown error')}"
            )

        return repo_path

    @staticmethod
    def bootstrap_environment(repo_path: Path, use_venv: bool = True) -> dict:
        """Bootstrap repository environment (install dependencies).

        Args:
            repo_path: Path to repository
            use_venv: If True, create per-task virtual environment

        Returns:
            Dict with "success" bool, "steps" list, and optional "error" string
        """
        import platform
        import sys

        steps = []
        pip_cmd = ["pip"]

        try:
            # Create per-task venv if requested
            if use_venv:
                env_dir = repo_path / ".apex_venv"
                if not env_dir.exists():
                    result = subprocess.run(
                        [sys.executable, "-m", "venv", str(env_dir)],
                        capture_output=True,
                        text=True,
                    )
                    steps.append(f"Create venv at {env_dir} (exit {result.returncode})")

                    if result.returncode == 0:
                        # Use venv pip
                        if platform.system() == "Windows":
                            pip_cmd = [str(env_dir / "Scripts" / "pip.exe")]
                        else:
                            pip_cmd = [str(env_dir / "bin" / "pip")]

                        # Upgrade pip/setuptools
                        result = subprocess.run(
                            pip_cmd + ["install", "-U", "pip", "wheel", "setuptools"],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        steps.append(f"Upgrade pip/wheel/setuptools (exit {result.returncode})")

            # Check for setup files
            has_pyproject = (repo_path / "pyproject.toml").exists()
            has_setup_py = (repo_path / "setup.py").exists()
            has_requirements = (repo_path / "requirements.txt").exists()

            # Try to install the package itself if setup file exists
            if has_pyproject or has_setup_py:
                result = subprocess.run(
                    pip_cmd + ["install", "-e", "."],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                steps.append(f"pip install -e . (exit {result.returncode})")

                if result.returncode != 0:
                    # Try without -e flag as fallback
                    result = subprocess.run(
                        pip_cmd + ["install", "."],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    steps.append(f"pip install . (exit {result.returncode})")

            # Install requirements if present
            if has_requirements:
                result = subprocess.run(
                    pip_cmd + ["install", "-r", "requirements.txt"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                steps.append(f"pip install -r requirements.txt (exit {result.returncode})")

            # Log environment if using venv
            if use_venv and pip_cmd != ["pip"]:
                try:
                    freeze_out = subprocess.check_output(
                        pip_cmd + ["freeze"],
                        cwd=repo_path,
                        text=True,
                        timeout=30,
                    )
                    artifacts_dir = repo_path.parent / "artifacts"
                    if artifacts_dir.exists():
                        (artifacts_dir / "pip_freeze.txt").write_text(
                            freeze_out, encoding="utf-8"
                        )
                    steps.append("Environment logged to pip_freeze.txt")
                except Exception:
                    pass  # Non-critical

            return {
                "success": True,
                "steps": steps,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "steps": steps,
                "error": "Environment bootstrap timed out",
            }
        except Exception as e:
            return {
                "success": False,
                "steps": steps,
                "error": str(e),
            }

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
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
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

            patch_strategy = "p0"
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

            patch_strategy = "p1"
            if result.returncode == 0:
                print(f"Patch applied using strategy: {patch_strategy}")
                return True

            # Reset again for 3-way attempt
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

            # Try 3-way merge as last resort
            result_3way = subprocess.run(
                ["git", "apply", "--3way", "--reject", "--whitespace=nowarn", patch_file],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if result_3way.returncode == 0:
                print("Patch applied using strategy: 3way")
                return True

            # Log failure - persist to artifacts if available
            stderr_log = f"p0/p1/3way all failed\n\n--- stderr ---\n{result_3way.stderr}\n"
            print(f"Patch application failed (tried p0, p1, 3way): {result_3way.stderr[:500]}")
            
            # Try to save to artifacts dir if it exists
            artifacts_dir = repo_path.parent / "artifacts"
            if artifacts_dir.exists():
                (artifacts_dir / "git_apply_stderr.txt").write_text(
                    stderr_log,
                    encoding="utf-8"
                )
            
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
                print("Warning: Test list too long for -k, running all tests")
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
