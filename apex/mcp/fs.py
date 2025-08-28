"""MCP File System Adapter with whitelisted root.

Provides safe file system operations within a sandboxed directory.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FSConfig:
    """File system adapter configuration."""

    root_dir: Path
    max_file_size: int = 1_000_000  # 1MB default
    allowed_extensions: Optional[List[str]] = None
    deny_patterns: List[str] = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.allowed_extensions is None:
            self.allowed_extensions = [".py", ".txt", ".json", ".md", ".yaml", ".yml"]
        if self.deny_patterns is None:
            self.deny_patterns = ["__pycache__", ".git", ".venv", "venv", ".env"]


class MCPFileSystem:
    """File system adapter with safety constraints.

    All operations are restricted to a whitelisted root directory.
    """

    def __init__(self, config: FSConfig):
        """Initialize file system adapter.

        Args:
            config: File system configuration
        """
        self.config = config
        self.root = Path(config.root_dir).resolve()

        # Create root if it doesn't exist
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path within root.

        Args:
            path: Path to validate

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If path escapes root
        """
        # Resolve to absolute path within root
        abs_path = (self.root / path).resolve()

        # Check if path is within root
        if not str(abs_path).startswith(str(self.root)):
            raise ValueError(f"Path escapes root: {path}")

        # Check deny patterns
        for pattern in self.config.deny_patterns:
            if pattern in str(abs_path):
                raise ValueError(f"Path contains denied pattern {pattern}: {path}")

        return abs_path

    async def read(self, path: str) -> str:
        """Read file contents.

        Args:
            path: File path relative to root

        Returns:
            File contents as string
        """
        abs_path = self._validate_path(path)

        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not abs_path.is_file():
            raise ValueError(f"Not a file: {path}")

        # Check file size
        size = abs_path.stat().st_size
        if size > self.config.max_file_size:
            raise ValueError(f"File too large ({size} bytes): {path}")

        # Read file
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, abs_path.read_text)

    async def write(self, path: str, content: str) -> bool:
        """Write file contents.

        Args:
            path: File path relative to root
            content: Content to write

        Returns:
            True if successful
        """
        abs_path = self._validate_path(path)

        # Check extension if specified
        if self.config.allowed_extensions:
            if not any(str(abs_path).endswith(ext) for ext in self.config.allowed_extensions):
                raise ValueError(f"File extension not allowed: {path}")

        # Check content size
        if len(content) > self.config.max_file_size:
            raise ValueError(f"Content too large ({len(content)} bytes)")

        # Create parent directories
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, abs_path.write_text, content)
        return True

    async def list_dir(self, path: str = ".") -> List[str]:
        """List directory contents.

        Args:
            path: Directory path relative to root

        Returns:
            List of file/directory names
        """
        abs_path = self._validate_path(path)

        if not abs_path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        # List contents
        items = []
        for item in abs_path.iterdir():
            # Skip denied patterns
            skip = False
            for pattern in self.config.deny_patterns:
                if pattern in str(item):
                    skip = True
                    break
            if not skip:
                items.append(item.name)

        return sorted(items)

    async def exists(self, path: str) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if exists
        """
        try:
            abs_path = self._validate_path(path)
            return abs_path.exists()
        except ValueError:
            return False

    async def delete(self, path: str) -> bool:
        """Delete file or empty directory.

        Args:
            path: Path to delete

        Returns:
            True if successful
        """
        abs_path = self._validate_path(path)

        if not abs_path.exists():
            return False

        if abs_path.is_file():
            abs_path.unlink()
        elif abs_path.is_dir():
            # Only delete if empty
            if any(abs_path.iterdir()):
                raise ValueError(f"Directory not empty: {path}")
            abs_path.rmdir()
        else:
            raise ValueError(f"Unknown path type: {path}")

        return True

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """Get file/directory metadata.

        Args:
            path: Path to check

        Returns:
            Metadata dictionary
        """
        abs_path = self._validate_path(path)

        if not abs_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        stat = abs_path.stat()
        return {
            "path": path,
            "type": "file" if abs_path.is_file() else "directory",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
        }


class AtomicFileWrite:
    """Context manager for atomic file writes.

    Writes to temporary file then renames on success.
    """

    def __init__(self, fs: MCPFileSystem, path: str):
        """Initialize atomic write.

        Args:
            fs: File system adapter
            path: Target file path
        """
        self.fs = fs
        self.path = path
        self.temp_path = f"{path}.tmp"
        self.content = None

    async def __aenter__(self):
        """Enter context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context, commit or rollback."""
        if exc_type is None and self.content is not None:
            # Success, write and rename
            await self.fs.write(self.temp_path, self.content)
            abs_temp = self.fs._validate_path(self.temp_path)
            abs_target = self.fs._validate_path(self.path)
            abs_temp.rename(abs_target)
        else:
            # Failure, cleanup temp file if exists
            try:
                await self.fs.delete(self.temp_path)
            except Exception:
                pass

    def set_content(self, content: str):
        """Set content to write atomically.

        Args:
            content: File content
        """
        self.content = content
