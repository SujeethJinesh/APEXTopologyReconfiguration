from __future__ import annotations

from typing import Protocol


class Test(Protocol):
    async def discover(self) -> list[str]: ...

    async def run(self, tests: list[str] | None = None, timeout_s: int = 120) -> dict: ...
