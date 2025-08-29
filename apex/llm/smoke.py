#!/usr/bin/env python3
"""Smoke test for LLM manager with parallel prompts."""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apex.config import defaults
from apex.llm.client import PortableLLMClient


async def smoke_test():
    """Run 5 parallel prompts to test LLM manager."""

    print("=== LLM Smoke Test ===")
    print(f"Backend: {defaults.LLM_BACKEND}")
    print(f"Instances: {defaults.LLM_NUM_INSTANCES}")
    print(f"Model path: {defaults.GGUF_MODEL_PATH or defaults.LLM_MODEL_ID}")
    print()

    # Check if we have a model path for non-stub mode
    if not defaults.LLM_STUB_MODE and defaults.LLM_BACKEND == "llama_cpp_metal":
        if not defaults.GGUF_MODEL_PATH or not os.path.exists(defaults.GGUF_MODEL_PATH):
            print("ERROR: APEX_GGUF_MODEL_PATH not set or file doesn't exist")
            print("Set it to your GGUF model path, e.g.:")
            print("export APEX_GGUF_MODEL_PATH=/path/to/model.gguf")
            return 1

    # Create client
    client = PortableLLMClient()

    print("Starting LLM manager and warming up instances...")
    t0 = time.time()

    # Ensure started (includes warmup)
    await client.ensure_started()

    warmup_time = time.time() - t0
    print(f"Warmup completed in {warmup_time:.1f}s")
    print()

    # Test prompts with unique markers
    prompts = [
        ("What is 2 + 2?", "Math"),
        ("Write a haiku about coding", "Poetry"),
        ("Explain recursion in one sentence", "CS"),
        ("What color is the sky?", "Trivia"),
        ("Define machine learning", "AI"),
    ]

    print(f"Running {len(prompts)} parallel prompts...")
    print()

    # Run prompts in parallel
    async def run_prompt(prompt, label, agent_id):
        """Run a single prompt."""
        t_start = time.time()
        response = await client.complete(
            prompt=prompt,
            max_tokens=50,
            agent_id=agent_id,
            session_id=f"smoke_{agent_id}",
        )
        t_elapsed = time.time() - t_start

        return {
            "label": label,
            "agent_id": agent_id,
            "prompt": prompt[:30] + "..." if len(prompt) > 30 else prompt,
            "response": (
                response.content[:100] + "..." if len(response.content) > 100 else response.content
            ),
            "tokens": response.tokens_used,
            "time_s": t_elapsed,
            "error": response.error,
        }

    # Create tasks
    tasks = [run_prompt(prompt, label, f"Agent_{i}") for i, (prompt, label) in enumerate(prompts)]

    # Run in parallel
    results = await asyncio.gather(*tasks)

    # Display results
    print("=== Results ===")
    for r in results:
        print(f"[{r['label']}] Agent: {r['agent_id']}")
        print(f"  Prompt: {r['prompt']}")
        print(f"  Response: {r['response']}")
        print(f"  Tokens: {r['tokens']}, Time: {r['time_s']:.2f}s")
        if r["error"]:
            print(f"  ERROR: {r['error']}")
        print()

    # Summary stats
    total_tokens = sum(r["tokens"] for r in results)
    avg_time = sum(r["time_s"] for r in results) / len(results)
    errors = sum(1 for r in results if r["error"])

    print("=== Summary ===")
    print(f"Total tokens used: {total_tokens}")
    print(f"Average response time: {avg_time:.2f}s")
    print(f"Errors: {errors}/{len(results)}")
    print(f"Token tracker: {client.get_stats()}")

    # Cleanup
    client.shutdown()

    return 0 if errors == 0 else 1


def main():
    """Main entry point."""
    # Parse simple args
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python -m apex.llm.smoke [--backend llama_cpp_metal|hf_cuda] [--instances N]")
        print()
        print("Environment variables:")
        print("  APEX_LLM_BACKEND: Backend to use (llama_cpp_metal or hf_cuda)")
        print("  APEX_NUM_LLM_INSTANCES: Number of instances (default 5)")
        print("  APEX_GGUF_MODEL_PATH: Path to GGUF model (for llama_cpp_metal)")
        print("  APEX_HF_MODEL_ID: HuggingFace model ID (for hf_cuda)")
        print("  APEX_LLM_STUB: Set to 1 for stub mode (no real model)")
        sys.exit(0)

    # Parse backend arg
    if "--backend" in sys.argv:
        idx = sys.argv.index("--backend")
        if idx + 1 < len(sys.argv):
            os.environ["APEX_LLM_BACKEND"] = sys.argv[idx + 1]

    # Parse instances arg
    if "--instances" in sys.argv:
        idx = sys.argv.index("--instances")
        if idx + 1 < len(sys.argv):
            os.environ["APEX_NUM_LLM_INSTANCES"] = sys.argv[idx + 1]

    # Run smoke test
    exit_code = asyncio.run(smoke_test())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
