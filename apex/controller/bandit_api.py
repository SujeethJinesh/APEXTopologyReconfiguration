from __future__ import annotations

from typing import Protocol


class BanditSwitch(Protocol):
    def decide(self, features: list[float]) -> dict: ...

    def update(self, features: list[float], action: int, reward: float) -> None: ...
