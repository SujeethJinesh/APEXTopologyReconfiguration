import asyncio
from typing import Tuple

import pytest
from aiohttp import web

from apex.integrations.llm.llm_http import HTTPLLM


async def _start_test_server(handler) -> Tuple[web.AppRunner, str]:
    app = web.Application()
    app.router.add_post("/generate", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    # discover the bound port
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_llm_http_success():
    async def handler(request):
        data = await request.json()
        prompt = data.get("prompt", "")
        max_tokens = int(data.get("max_tokens", 0))
        return web.json_response(
            {
                "text": prompt.upper(),
                "tokens_in": len(prompt.split()),
                "tokens_out": min(max_tokens, 5),
            }
        )

    runner, base = await _start_test_server(handler)
    try:
        async with HTTPLLM(base, timeout_s=2.0, retries=0) as llm:
            resp = await llm.generate("hello world", 32)
            assert resp["text"] == "HELLO WORLD"
            assert resp["tokens_in"] == 2
            assert resp["tokens_out"] == 5
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_llm_http_retry_on_5xx():
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return web.Response(status=500)
        return web.json_response({"text": "ok", "tokens_in": 1, "tokens_out": 1})

    runner, base = await _start_test_server(handler)
    try:
        async with HTTPLLM(base, timeout_s=2.0, retries=1) as llm:
            resp = await llm.generate("x", 1)
            assert resp["text"] == "ok"
            assert calls["n"] == 2
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_llm_http_timeout():
    async def handler(request):
        await asyncio.sleep(0.2)
        return web.json_response({"text": "late", "tokens_in": 1, "tokens_out": 1})

    runner, base = await _start_test_server(handler)
    try:
        async with HTTPLLM(base, timeout_s=0.05, retries=0) as llm:
            with pytest.raises(asyncio.TimeoutError):
                await llm.generate("x", 1)
    finally:
        await runner.cleanup()
