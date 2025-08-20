from __future__ import annotations

from typing import Protocol

from .message import Epoch


class ISwitchEngine(Protocol):
    def active(self) -> tuple[str, Epoch]: ...

    async def switch_to(self, target: str) -> dict: ...
