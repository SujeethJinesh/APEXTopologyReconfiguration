"""Repository manager for SWE-bench evaluation."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


class RepoManager:
    """Manages git repository checkouts for evaluation."""

    def __init__(
        self,
        work_root: Path,
        cache_env: str = "APEX_REPO_CACHE",
        gh_token_env: str = "GITHUB_TOKEN",
    ):
        """Initialize repo manager.

        Args:
            work_root: Root directory for working copies
            cache_env: Environment variable for repo cache directory
            gh_token_env: Environment variable for GitHub token
        """
        self.work_root = Path(work_root)
        self.work_root.mkdir(parents=True, exist_ok=True)

        # Use cache directory from env or default to work_root/cache
        cache_dir = os.getenv(cache_env)
        if cache_dir:
            self.cache_root = Path(cache_dir)
        else:
            self.cache_root = self.work_root / "cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)

        # GitHub token for authenticated access (higher rate limits)
        self.gh_token = os.getenv(gh_token_env, "")

    def prepare_checkout(self, repo_slug: str, commit: str) -> Path:
        """Prepare a checkout of a repository at a specific commit.

        Args:
            repo_slug: Repository slug (e.g., "psf/requests")
            commit: Commit hash to checkout

        Returns:
            Path to the checked-out repository
        """
        # Create cache key from repo and commit
        org, repo_name = repo_slug.split("/")
        cache_key = f"{org}__{repo_name}@{commit[:8]}"
        checkout_dir = self.work_root / cache_key

        # If already checked out, just clean and reset
        if checkout_dir.exists() and (checkout_dir / ".git").exists():
            self._reset_repo(checkout_dir, commit)
            return checkout_dir

        # Clone fresh copy
        checkout_dir.mkdir(parents=True, exist_ok=True)
        repo_url = self._build_repo_url(repo_slug)

        try:
            # Clone repository
            subprocess.run(
                ["git", "clone", repo_url, str(checkout_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for clone
            )

            # Checkout specific commit
            subprocess.run(
                ["git", "checkout", commit],
                cwd=checkout_dir,
                check=True,
                capture_output=True,
                text=True,
            )

            # Clean any untracked files
            subprocess.run(
                ["git", "clean", "-xdf"],
                cwd=checkout_dir,
                check=True,
                capture_output=True,
                text=True,
            )

        except subprocess.CalledProcessError as e:
            # Clean up on failure
            if checkout_dir.exists():
                import shutil

                shutil.rmtree(checkout_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to prepare checkout: {e.stderr}")

        return checkout_dir

    def apply_patch(self, repo_path: Path, patch_content: str, patch_type: str = "test") -> bool:
        """Apply a patch to a repository.

        Args:
            repo_path: Path to repository
            patch_content: Patch content (unified diff format)
            patch_type: Type of patch ("test" or "solution")

        Returns:
            True if patch applied successfully, False otherwise
        """
        if not patch_content.strip():
            return True  # Empty patch is considered success

        # Write patch to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=f"_{patch_type}.patch", delete=False
        ) as f:
            f.write(patch_content)
            patch_file = f.name

        try:
            # Apply patch using git apply
            result = subprocess.run(
                ["git", "apply", "--index", "--whitespace=fix", patch_file],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0

            if not success:
                # Log failure reason
                print(f"Patch application failed: {result.stderr}")

            return success

        except subprocess.TimeoutExpired:
            print("Patch application timed out")
            return False

        finally:
            # Clean up temp file
            if os.path.exists(patch_file):
                os.unlink(patch_file)

    def run_tests(self, repo_path: Path, timeout: int = 120) -> tuple[bool, str]:
        """Run tests in a repository.

        Args:
            repo_path: Path to repository
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, output)
        """
        try:
            # Simple pytest runner for MVP
            result = subprocess.run(
                ["pytest", "-xvs", "--tb=short", "-q"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            return success, output

        except subprocess.TimeoutExpired:
            return False, "Test execution timed out"
        except FileNotFoundError:
            # pytest not installed or not in PATH
            # Try python -m pytest as fallback
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", "-xvs", "--tb=short", "-q"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                success = result.returncode == 0
                output = result.stdout + result.stderr
                return success, output
            except Exception as e:
                return False, f"Failed to run tests: {e}"

    def _reset_repo(self, repo_path: Path, commit: str):
        """Reset repository to specific commit and clean."""
        # Fetch latest changes
        subprocess.run(["git", "fetch"], cwd=repo_path, capture_output=True, text=True, timeout=60)

        # Reset to commit
        subprocess.run(
            ["git", "reset", "--hard", commit],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

        # Clean untracked files
        subprocess.run(["git", "clean", "-xdf"], cwd=repo_path, capture_output=True, text=True)

    def _build_repo_url(self, repo_slug: str) -> str:
        """Build repository URL with optional authentication."""
        if self.gh_token:
            # Use authenticated URL for higher rate limits
            return f"https://{self.gh_token}@github.com/{repo_slug}.git"
        else:
            # Use unauthenticated HTTPS
            return f"https://github.com/{repo_slug}.git"
