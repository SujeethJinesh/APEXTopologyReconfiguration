#!/usr/bin/env python3
"""Quick MCP adapter smoke test with LLM."""

import asyncio
import json
import time
from pathlib import Path

from apex.llm.client import PortableLLMClient
from apex.mcp.fs import MCPFileSystem, FSConfig
from apex.mcp.test import MCPTestRunner, TestConfig
from apex.eval.progress import ProgressTracker, ProgressEvent


async def run_mcp_smoke():
    """Run a simple episode with MCP adapters and LLM."""
    
    # Initialize components
    llm = PortableLLMClient()
    fs_config = FSConfig(root_dir=Path("/tmp/apex_smoke"))
    fs_adapter = MCPFileSystem(fs_config)
    test_config = TestConfig(timeout_seconds=30)
    test_adapter = MCPTestRunner(test_config)
    tracker = ProgressTracker(
        episode_id="smoke_001",
        episode_timeout_s=300,
        progress_extend_s=30,
    )
    
    print("=== MCP Smoke Test ===")
    print(f"Episode: {tracker.episode_id}")
    print(f"Timeout: {tracker.episode_timeout_s}s (extends by {tracker.progress_extend_s}s)")
    print()
    
    # Ensure LLM is ready
    print("Starting LLM instances...")
    await llm.ensure_started()
    
    # Create test file
    print("Testing FileSystem adapter...")
    await fs_adapter.write("test.py", "def add(a, b):\n    return a + b\n")
    content = await fs_adapter.read("test.py")
    print(f"  Wrote and read file: {len(content)} chars")
    tracker.record_progress(ProgressEvent.FILE_WRITTEN)
    
    # Run test
    print("Testing Test adapter...")
    test_result = await test_adapter.run_pytest("/tmp/apex_smoke")
    print(f"  Test result: passed={test_result.get('passed', False)}, output={len(test_result.get('output', ''))} chars")
    tracker.record_progress(ProgressEvent.TEST_RUN, {"passed": test_result.get('passed', False)})
    
    # LLM call
    print("Testing LLM...")
    response = await llm.complete(
        prompt="Write a simple Python function to multiply two numbers",
        max_tokens=50,
        agent_id="smoke_agent",
        session_id=tracker.episode_id,
    )
    print(f"  LLM response: {len(response.content)} chars, {response.tokens_used} tokens")
    tracker.record_progress(ProgressEvent.LLM_RESPONSE, {"tokens": response.tokens_used})
    
    # Check budget
    stats = llm.get_stats()
    print(f"  Budget used: {stats['tokens_used']}/{stats['budget']}")
    
    # Build result
    result = {
        "__meta__": {
            "llm_backend": stats["backend"],
            "instances": stats["num_instances"],
            "episode_id": tracker.episode_id,
        },
        "success": test_result.get('passed', False),
        "tokens_used": stats["tokens_used"],
        "budget": stats["budget"],
        "progress_events": len(tracker.events),
        "mcp_calls": {
            "fs_write": 1,
            "fs_read": 1,
            "test_run": 1,
        },
        "worker_pids": []  # Would be populated from WORKER_READY logs
    }
    
    # Write result
    output_path = Path("artifacts/local/mcp_smoke.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f)
        f.write("\n")
    
    print(f"\nResult written to: {output_path}")
    print(json.dumps(result, indent=2))
    
    llm.shutdown()
    return result


if __name__ == "__main__":
    asyncio.run(run_mcp_smoke())