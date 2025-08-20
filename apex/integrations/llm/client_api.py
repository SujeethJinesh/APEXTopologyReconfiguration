from __future__ import annotations

from typing import Protocol


class LLM(Protocol):
    async def generate(self, prompt: str, max_tokens: int) -> dict: ...
