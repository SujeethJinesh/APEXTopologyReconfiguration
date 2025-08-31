#!/usr/bin/env python3
"""Verify real LLM loading with memory tracking and PID verification."""

import asyncio
import json
import os
import time
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.llm.client import LLMClient  # alias to PortableLLMClient


async def main():
    """Verify LLM backend is real and workers are loaded."""
    
    # Check environment
    backend = os.getenv("APEX_LLM_BACKEND", "unknown")
    num_instances = int(os.getenv("APEX_NUM_LLM_INSTANCES", "3"))
    warmup_tokens = int(os.getenv("APEX_WARMUP_TOKENS", "128"))
    
    print(f"[VERIFY] Configuration:")
    print(f"  Backend: {backend}")
    print(f"  Instances: {num_instances}")
    print(f"  Warmup tokens: {warmup_tokens}")
    print(f"  Model path: {os.getenv('APEX_GGUF_MODEL_PATH', 'auto-download')}")
    print()
    
    # Block stub mode
    if backend == "stub":
        raise SystemExit("[VERIFY] ERROR: Cannot verify with stub backend. Set APEX_LLM_BACKEND=llama_cpp_metal")
    
    # Create client
    print("[VERIFY] Creating LLM client...")
    llm = LLMClient()
    
    # Warmup with meaningful tokens
    print(f"[VERIFY] Starting warmup ({warmup_tokens} tokens per worker)...")
    t0 = time.time()
    await llm.warmup_all()  # Uses enhanced warmup
    warmup_time = time.time() - t0
    print(f"[VERIFY] Warmup completed in {warmup_time:.2f}s")
    print()
    
    # Test generation on each worker
    print("[VERIFY] Testing generation on each worker...")
    prompts = [
        "Write exactly three words.",
        "Count to five.",
        "Name a color."
    ]
    
    tasks = []
    for i in range(num_instances):
        agent_id = f"agent::{i}"
        prompt = prompts[i % len(prompts)]
        tasks.append(llm.complete(prompt, max_tokens=24, agent_id=agent_id))
    
    responses = await asyncio.gather(*tasks)
    
    # Analyze responses
    print("\n[VERIFY] Worker responses:")
    print("-" * 80)
    
    pids_seen = set()
    for i, resp in enumerate(responses):
        # Extract info from response
        if hasattr(resp, '__dict__'):
            resp_dict = resp.__dict__
        else:
            resp_dict = resp
        
        # Get backend info from the raw response if available
        backend_info = {}
        if 'backend_info' in resp_dict:
            backend_info = resp_dict['backend_info']
        elif hasattr(resp, 'backend_info'):
            backend_info = resp.backend_info
        
        # Get PID and memory
        pid = backend_info.get('pid', 'unknown')
        instance_id = backend_info.get('instance_id', i)
        rss = backend_info.get('rss', 0)
        model_size = backend_info.get('model_size_bytes', 0)
        
        if pid != 'unknown':
            pids_seen.add(pid)
        
        # Format memory sizes
        rss_mb = rss / (1024 * 1024) if rss else 0
        model_gb = model_size / (1024 * 1024 * 1024) if model_size else 0
        
        print(f"Worker {i} (instance_id={instance_id}):")
        print(f"  PID: {pid}")
        print(f"  RSS: {rss_mb:.1f} MB")
        print(f"  Model size: {model_gb:.2f} GB")
        print(f"  Response: '{resp.content[:50]}...' ({resp.tokens_used} tokens)")
        
        # Log full backend info as JSON
        if backend_info:
            print(f"  [VERIFY/RESP] {json.dumps(backend_info)}")
        print()
    
    # Summary
    print("-" * 80)
    print(f"[VERIFY] Summary:")
    print(f"  Unique PIDs: {len(pids_seen)} (expected {num_instances})")
    print(f"  PIDs: {sorted(pids_seen)}")
    print(f"  Warmup time: {warmup_time:.2f}s")
    
    # Validate
    if len(pids_seen) != num_instances:
        print(f"[VERIFY] WARNING: Expected {num_instances} unique PIDs, got {len(pids_seen)}")
    
    if not pids_seen:
        print("[VERIFY] ERROR: No PIDs detected - backend may not be returning metadata")
        return 1
    
    print("\n[VERIFY] ✅ Verification complete")
    
    # Get stats
    stats = llm.get_stats()
    print(f"\n[VERIFY] Client stats:")
    print(json.dumps(stats, indent=2))
    
    # Shutdown
    llm.shutdown()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)