from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import List, Optional

from .test_api import Test


class PytestAdapter(Test):
    """
    Test adapter that shells out to pytest in a subprocess.

    - discover(): python -m pytest --collect-only -q
      returns a sorted list of nodeids
    - run(selected, timeout_s): python -m pytest -q [selected...]
      returns {passed, failed, skipped, errors, duration_s, timed_out, stdout}
    """

    def __init__(self, workdir: str) -> None:
        self._workdir = Path(workdir)

    async def _run_subprocess(
        self, args: List[str], timeout_s: int
    ) -> tuple[int, str, str, float, bool]:
        t0 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            *args,
            cwd=str(self._workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out = await asyncio.wait_for(proc.stdout.read(), timeout=timeout_s)
            code = await asyncio.wait_for(proc.wait(), timeout=timeout_s)
            timed_out = False
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass  # Process didn't terminate cleanly, but we tried
            timed_out = True
            out = b""
            code = -1
        duration = max(0.0, time.monotonic() - t0)
        return code, out.decode("utf-8", errors="ignore"), "", duration, timed_out

    async def discover(self) -> List[str]:
        code, stdout, _, _, _ = await self._run_subprocess(["--collect-only", "-q"], timeout_s=60)
        # pytest -q --collect-only prints nodeids, one per line
        nodeids = [line.strip() for line in stdout.splitlines() if "::" in line]
        nodeids.sort()
        return nodeids

    async def run(self, selected: Optional[List[str]] = None, timeout_s: int = 120) -> dict:
        args: List[str] = ["-q"]
        if selected:
            args.extend(selected)
        code, stdout, _, duration, timed_out = await self._run_subprocess(args, timeout_s=timeout_s)

        # Parse summary like: "2 passed, 1 failed, 1 skipped in 0.12s"
        passed = failed = skipped = errors = 0
        text = ""
        for line in stdout.splitlines()[::-1]:
            has_test_types = any(
                word in line for word in ["passed", "failed", "skipped", "error", "errors"]
            )
            if " in " in line and has_test_types:
                text = line
                break

        import re

        def _extract(label: str) -> int:
            m = re.search(rf"(\d+)\s+{label}\b", text)
            return int(m.group(1)) if m else 0

        passed = _extract("passed")
        failed = _extract("failed")
        skipped = _extract("skipped")
        errors = _extract("errors") or _extract("error")

        # Extract duration
        m = re.search(r"in\s+([0-9.]+)s", text)
        duration_s = float(m.group(1)) if m else duration

        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "duration_s": duration_s,
            "timed_out": timed_out,
            "stdout": stdout,
        }
