from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp

from .client_api import LLM


class HTTPLLM(LLM):
    """
    Minimal HTTP LLM client (no pooling). POSTs to {base_url}/generate.

    Usage:
        async with HTTPLLM("http://127.0.0.1:8080", timeout_s=5.0, retries=1) as llm:
            resp = await llm.generate("hello", 64)
    """

    def __init__(self, base_url: str, timeout_s: float = 30.0, retries: int = 1) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = float(timeout_s)
        self._retries = int(retries)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "HTTPLLM":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def generate(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        if self._session is None:
            # allow use without context manager
            timeout = aiohttp.ClientTimeout(total=self._timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)

        url = f"{self._base_url}/generate"
        payload = {"prompt": prompt, "max_tokens": int(max_tokens)}

        last_exc: Optional[Exception] = None
        tries = self._retries + 1
        for attempt in range(tries):
            try:
                async with self._session.post(url, json=payload) as resp:
                    if 500 <= resp.status < 600:
                        # transient; retry if any left
                        if attempt < tries - 1:
                            continue
                        resp.raise_for_status()
                    data = await resp.json()
                    # Expect text/tokens_in/tokens_out
                    return {
                        "text": data.get("text", ""),
                        "tokens_in": int(data.get("tokens_in", 0)),
                        "tokens_out": int(data.get("tokens_out", 0)),
                    }
            except asyncio.TimeoutError:
                # surface timeouts
                raise
            except Exception as e:
                last_exc = e
                if attempt < tries - 1:
                    continue
                raise
        # unreachable
        raise last_exc if last_exc else RuntimeError("LLM request failed")
