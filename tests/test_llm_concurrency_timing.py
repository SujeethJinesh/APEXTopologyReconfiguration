"""Test true parallel execution with wall-clock timing."""

import asyncio
import time

import pytest

from apex.llm.client import PortableLLMClient


@pytest.mark.asyncio
async def test_parallel_speedup():
    """Verify parallel execution is faster than sequential."""
    client = PortableLLMClient()
    
    # Prepare 3 prompts that each take ~1-2 seconds
    prompts = [
        "Generate exactly 100 tokens about space exploration",
        "Generate exactly 100 tokens about machine learning",
        "Generate exactly 100 tokens about quantum computing",
    ]
    
    # Run sequentially and time it
    sequential_start = time.time()
    sequential_results = []
    for i, prompt in enumerate(prompts):
        result = await client.complete(
            prompt=prompt,
            max_tokens=100,
            agent_id=f"sequential_{i}"
        )
        sequential_results.append(result)
    sequential_time = time.time() - sequential_start
    
    # Run in parallel and time it
    parallel_start = time.time()
    parallel_tasks = [
        client.complete(
            prompt=prompt,
            max_tokens=100,
            agent_id=f"parallel_{i}"
        )
        for i, prompt in enumerate(prompts)
    ]
    parallel_results = await asyncio.gather(*parallel_tasks)
    parallel_time = time.time() - parallel_start
    
    # Verify parallel is significantly faster
    speedup = sequential_time / parallel_time
    print(f"Sequential: {sequential_time:.2f}s")
    print(f"Parallel: {parallel_time:.2f}s")
    print(f"Speedup: {speedup:.2f}x")
    
    # Should be at least 1.5x faster (conservative due to overhead)
    assert speedup > 1.5, f"Parallel not faster: {speedup:.2f}x"
    
    # Verify all requests completed
    assert len(parallel_results) == 3
    assert all(r.content for r in parallel_results)
    
    client.shutdown()


@pytest.mark.asyncio
async def test_worker_pid_logging(capfd):
    """Verify worker PIDs are logged on initialization."""
    client = PortableLLMClient()
    await client.ensure_started()
    
    # Capture stdout
    captured = capfd.readouterr()
    
    # Look for worker ready logs
    worker_lines = [line for line in captured.out.split('\n') if '[WORKER_READY]' in line]
    
    # Should have as many workers as instances
    assert len(worker_lines) >= client.config.num_instances
    
    # Parse and verify unique PIDs
    import json
    pids = set()
    for line in worker_lines:
        if '[WORKER_READY]' in line:
            json_str = line.split('[WORKER_READY]')[1].strip()
            info = json.loads(json_str)
            pids.add(info['pid'])
    
    # All PIDs should be unique
    assert len(pids) == client.config.num_instances
    
    client.shutdown()