from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Dict, List, Optional


class StubFS:
    """Stub filesystem implementation for testing."""

    def __init__(self, root: Path):
        self.root = root
        self.files: Dict[str, bytes] = {}

    async def read_file(self, path: str) -> bytes:
        """Read a file from the stub filesystem."""
        full_path = self.root / path
        if full_path.exists():
            return full_path.read_bytes()
        elif path in self.files:
            return self.files[path]
        else:
            raise FileNotFoundError(f"File not found: {path}")

    async def write_file(self, path: str, data: bytes) -> None:
        """Write a file to the stub filesystem."""
        full_path = self.root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        self.files[path] = data

    async def patch_file(self, path: str, diff: str) -> None:
        """Apply a patch to a file (simplified for testing)."""
        # Read current content
        content = await self.read_file(path)
        content_str = content.decode("utf-8")

        # Simple patch logic for our test case
        if "return a - b" in content_str:
            content_str = content_str.replace("return a - b", "return a + b")

        # Write back
        await self.write_file(path, content_str.encode("utf-8"))

    async def search_files(self, root: str, regex: str) -> List[str]:
        """Search for files matching a regex pattern."""
        pattern = re.compile(regex)
        results = []
        root_path = self.root / root

        if root_path.exists():
            for file_path in root_path.glob("**/*"):
                if file_path.is_file() and pattern.search(str(file_path)):
                    results.append(str(file_path.relative_to(self.root)))

        return results


class StubTest:
    """Stub test runner implementation for testing."""

    def __init__(self, root: Path):
        self.root = root
        self.test_files: List[str] = []

    async def discover(self) -> List[str]:
        """Discover test files."""
        test_dir = self.root / "tests"
        if test_dir.exists():
            self.test_files = [str(f.relative_to(self.root)) for f in test_dir.glob("test_*.py")]
        return self.test_files

    async def run(self, tests: Optional[List[str]] = None, timeout_s: int = 120) -> dict:
        """Run tests and return results."""
        # Simulate test run
        await asyncio.sleep(0.001)  # Tiny delay to simulate work

        # Check if the bug is fixed
        app_file = self.root / "src" / "app.py"
        if app_file.exists():
            content = app_file.read_text()
            if "return a + b" in content:
                # Bug is fixed, tests pass
                return {
                    "passed": 1,
                    "failed": 0,
                    "failures": [],
                }
            else:
                # Bug not fixed, tests fail
                return {
                    "passed": 0,
                    "failed": 1,
                    "failures": ["test_add"],
                }

        # No app file, tests fail
        return {
            "passed": 0,
            "failed": 1,
            "failures": ["test_add"],
        }


class StubLLM:
    """Stub LLM implementation for testing."""

    async def generate(self, prompt: str, max_tokens: int) -> dict:
        """Generate a deterministic response."""
        return {
            "text": "Fix the bug in the add function by changing subtraction to addition.",
            "tokens_used": 15,
        }
