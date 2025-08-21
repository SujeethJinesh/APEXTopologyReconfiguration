from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import List

from .fs_api import FS


class LocalFS(FS):
    """
    Local filesystem adapter with path whitelist enforcement.

    All operations are restricted to the whitelist root provided at construction.
    """

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve(strict=False)

    # -------- internal helpers --------

    def _resolve(self, rel_path: str) -> Path:
        p = (self._root / rel_path).resolve(strict=False)
        try:
            p.relative_to(self._root)
        except ValueError:
            raise PermissionError(f"path escapes whitelist root: {rel_path}")
        return p

    # -------- FS API --------

    async def read_file(self, path: str) -> bytes:
        abspath = self._resolve(path)

        def _read() -> bytes:
            return abspath.read_bytes()

        return await asyncio.to_thread(_read)

    async def write_file(self, path: str, data: bytes) -> None:
        abspath = self._resolve(path)

        def _write() -> None:
            abspath.parent.mkdir(parents=True, exist_ok=True)
            abspath.write_bytes(data)

        await asyncio.to_thread(_write)

    async def patch_file(self, path: str, diff: str) -> None:
        """
        Apply a simplified unified-diff:
          - support exactly one '-' line (old substring) and one '+' line (new substring)
          - perform a single replacement in the file contents

        Example diff:
            --- a/file.txt
            +++ b/file.txt
            @@
            - world
            + APEX
            @@
        """
        # Extract first '- ' and '+ ' payload lines
        old_sub, new_sub = None, None
        for line in diff.splitlines():
            if line.startswith("- "):
                old_sub = line[2:]
            elif line.startswith("+ "):
                new_sub = line[2:]
        if old_sub is None or new_sub is None:
            raise ValueError("unsupported diff format; need one '-' and one '+' line")

        abspath = self._resolve(path)

        def _patch() -> None:
            text = abspath.read_text(encoding="utf-8")
            if old_sub not in text:
                raise ValueError("old substring not found in file")
            text = text.replace(old_sub, new_sub, 1)
            abspath.write_text(text, encoding="utf-8")

        await asyncio.to_thread(_patch)

    async def search_files(self, root: str, regex: str) -> List[str]:
        """
        Search file contents under (whitelisted_root / root) for regex occurrences.
        Returns relative paths (to whitelist root) of files whose contents match.
        Results are sorted for deterministic output.
        """
        subroot = self._resolve(root)
        pattern = re.compile(regex)

        def _scan() -> List[str]:
            out: List[str] = []
            for dirpath, _, filenames in os.walk(subroot, followlinks=False):
                for fn in filenames:
                    p = Path(dirpath) / fn
                    try:
                        # Resolve symlinks and validate target is still under root
                        rp = p.resolve(strict=False)
                        rp.relative_to(self._root)  # Will raise if outside root
                    except Exception:
                        continue  # Skip files that escape the root
                    try:
                        content = rp.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if pattern.search(content):
                        rel = rp.relative_to(self._root).as_posix()
                        out.append(rel)
            out.sort()  # Ensure deterministic results
            return out

        return await asyncio.to_thread(_scan)
