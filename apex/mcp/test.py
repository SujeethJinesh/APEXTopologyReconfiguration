"""MCP Test Execution Adapter with sandbox and timeout.

Provides safe test execution within controlled environment.
"""

import asyncio
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TestConfig:
    """Test execution configuration."""

    timeout_seconds: int = 30
    max_output_size: int = 100_000  # 100KB
    python_path: str = "python3"
    allowed_commands: List[str] = None
    env_vars: Dict[str, str] = None
    working_dir: Optional[Path] = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.allowed_commands is None:
            self.allowed_commands = ["pytest", "python", "python3", "pip"]
        if self.env_vars is None:
            self.env_vars = {}


class MCPTestRunner:
    """Test execution adapter with safety constraints.

    Runs tests in subprocess with timeout and output limits.
    """

    def __init__(self, config: TestConfig):
        """Initialize test runner.

        Args:
            config: Test execution configuration
        """
        self.config = config

    async def run_pytest(
        self, test_path: str, args: Optional[List[str]] = None, working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run pytest on specified test file.

        Args:
            test_path: Path to test file
            args: Additional pytest arguments
            working_dir: Working directory for test

        Returns:
            Test result dictionary
        """
        if args is None:
            args = ["-xvs", "--tb=short"]

        cmd = [self.config.python_path, "-m", "pytest", test_path] + args
        return await self._run_command(cmd, working_dir)

    async def run_python(
        self, script: str, args: Optional[List[str]] = None, working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run Python script.

        Args:
            script: Python script content or path
            args: Script arguments
            working_dir: Working directory

        Returns:
            Execution result dictionary
        """
        if args is None:
            args = []

        # Check if script is a path or content
        if os.path.exists(script):
            # Run script file
            cmd = [self.config.python_path, script] + args
            return await self._run_command(cmd, working_dir)
        else:
            # Run script content via stdin
            return await self._run_script(script, args, working_dir)

    async def _run_command(
        self, cmd: List[str], working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run command in subprocess with timeout.

        Args:
            cmd: Command and arguments
            working_dir: Working directory

        Returns:
            Result dictionary
        """
        # Validate command
        base_cmd = os.path.basename(cmd[0])
        if base_cmd not in self.config.allowed_commands:
            return {
                "success": False,
                "error": f"Command not allowed: {base_cmd}",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "elapsed_seconds": 0,
            }

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.env_vars)

        # Set working directory
        cwd = working_dir or self.config.working_dir or os.getcwd()

        # Run command with timeout
        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )

            # Wait with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.config.timeout_seconds
            )

            # Decode and truncate output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if len(stdout_str) > self.config.max_output_size:
                stdout_str = stdout_str[: self.config.max_output_size] + "\n[OUTPUT TRUNCATED]"
            if len(stderr_str) > self.config.max_output_size:
                stderr_str = stderr_str[: self.config.max_output_size] + "\n[OUTPUT TRUNCATED]"

            elapsed = time.time() - start_time

            return {
                "success": proc.returncode == 0,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": proc.returncode,
                "elapsed_seconds": elapsed,
                "command": " ".join(cmd),
            }

        except asyncio.TimeoutError:
            # Kill process on timeout
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

            elapsed = time.time() - start_time
            return {
                "success": False,
                "error": f"Command timed out after {self.config.timeout_seconds}s",
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "elapsed_seconds": elapsed,
                "command": " ".join(cmd),
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "elapsed_seconds": elapsed,
                "command": " ".join(cmd),
            }

    async def _run_script(
        self, script_content: str, args: List[str], working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run Python script from content.

        Args:
            script_content: Python script as string
            args: Script arguments
            working_dir: Working directory

        Returns:
            Result dictionary
        """
        # Create temporary file for script
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            script_path = f.name

        try:
            # Run script file
            cmd = [self.config.python_path, script_path] + args
            return await self._run_command(cmd, working_dir)
        finally:
            # Cleanup temp file
            try:
                os.unlink(script_path)
            except Exception:
                pass

    async def check_syntax(self, code: str) -> Dict[str, Any]:
        """Check Python syntax without executing.

        Args:
            code: Python code to check

        Returns:
            Validation result
        """
        try:
            compile(code, "<string>", "exec")
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": f"Syntax error at line {e.lineno}: {e.msg}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def discover_tests(self, test_dir: str) -> List[str]:
        """Discover test files in directory.

        Args:
            test_dir: Directory to search for tests

        Returns:
            List of test file paths
        """
        test_files = []
        test_path = Path(test_dir)

        if test_path.exists() and test_path.is_dir():
            # Find all test_*.py and *_test.py files
            test_files.extend(str(p) for p in test_path.glob("test_*.py"))
            test_files.extend(str(p) for p in test_path.glob("*_test.py"))
            test_files.extend(str(p) for p in test_path.rglob("test_*.py"))
            test_files.extend(str(p) for p in test_path.rglob("*_test.py"))

        return sorted(list(set(test_files)))

    async def run_tests(
        self, test_paths: Optional[List[str]] = None, timeout_s: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run tests and return structured results.

        Args:
            test_paths: Specific test files to run (None = discover)
            timeout_s: Override timeout

        Returns:
            Structured test results with pass/fail counts
        """
        _ = timeout_s or self.config.timeout_seconds  # Will use in subprocess call

        if test_paths is None:
            # Discover tests in current directory
            test_paths = await self.discover_tests(".")

        if not test_paths:
            return {
                "success": False,
                "error": "No tests found",
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "duration": 0.0,
            }

        # Run pytest with JSON output for structured parsing
        cmd = [
            self.config.python_path,
            "-m",
            "pytest",
            "--tb=short",
            "-q",  # Quiet mode
            *test_paths,
        ]

        start_time = time.time()
        result = await self._run_command(cmd)
        duration = time.time() - start_time

        # Parse pytest output for test counts
        output = result.get("stdout", "")

        # Parse summary line (e.g., "3 passed, 1 failed, 2 skipped in 1.23s")
        passed = 0
        failed = 0
        skipped = 0

        # Look for pytest summary patterns
        if match := re.search(r"(\d+) passed", output):
            passed = int(match.group(1))
        if match := re.search(r"(\d+) failed", output):
            failed = int(match.group(1))
        if match := re.search(r"(\d+) skipped", output):
            skipped = int(match.group(1))

        total = passed + failed + skipped

        return {
            "success": failed == 0 and total > 0,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "duration": duration,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1),
        }


class TestSandbox:
    """Sandboxed test execution environment.

    Creates isolated directory for test execution.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize sandbox.

        Args:
            base_dir: Base directory for sandboxes
        """
        self.base_dir = base_dir or Path(tempfile.gettempdir())
        self.sandbox_dir: Optional[Path] = None

    async def __aenter__(self):
        """Create sandbox directory."""
        # Create unique sandbox directory
        self.sandbox_dir = Path(tempfile.mkdtemp(prefix="apex_test_", dir=self.base_dir))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup sandbox directory."""
        if self.sandbox_dir and self.sandbox_dir.exists():
            # Remove sandbox directory
            import shutil

            try:
                shutil.rmtree(self.sandbox_dir)
            except Exception:
                pass

    @property
    def path(self) -> Path:
        """Get sandbox directory path."""
        if not self.sandbox_dir:
            raise RuntimeError("Sandbox not initialized")
        return self.sandbox_dir

    async def write_file(self, name: str, content: str):
        """Write file to sandbox.

        Args:
            name: File name
            content: File content
        """
        file_path = self.path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, file_path.write_text, content)

    async def read_file(self, name: str) -> str:
        """Read file from sandbox.

        Args:
            name: File name

        Returns:
            File content
        """
        file_path = self.path / name

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, file_path.read_text)
