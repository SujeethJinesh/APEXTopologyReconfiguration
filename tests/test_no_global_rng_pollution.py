"""Test that evaluation harness does not pollute global RNG state."""

import random

from apex.eval.harness import EvalHarness


def test_no_global_rng_pollution():
    """Verify EvalHarness does not mutate the process-global RNG state."""
    # Capture global RNG state before
    s0 = random.getstate()

    # Create harness and run operations that might pollute RNG
    h = EvalHarness(mode="stub", seed=123)
    tasks = h.load_tasks(15)  # Force repetition to test suffix generation
    
    # Optionally run a dry episode if needed
    if tasks:
        _ = h.run_episode(
            tasks[0], 
            policy="static_star", 
            budget=10000
        )

    # Capture global RNG state after
    s1 = random.getstate()
    
    # States must be identical - no global mutation allowed
    assert s1 == s0, "EvalHarness must not mutate the process-global RNG state"


def test_harness_uses_instance_rng():
    """Verify harness uses its own RNG instance for determinism."""
    # Two harnesses with same seed should produce identical results
    h1 = EvalHarness(mode="stub", seed=42)
    h2 = EvalHarness(mode="stub", seed=42)
    
    tasks1 = h1.load_tasks(5)
    tasks2 = h2.load_tasks(5)
    
    # Task IDs should be identical
    ids1 = [t.task_id for t in tasks1]
    ids2 = [t.task_id for t in tasks2]
    assert ids1 == ids2, "Same seed should produce same task order"
    
    # Run episodes and check determinism
    result1 = h1.run_episode(tasks1[0], "static_star", 10000)
    result2 = h2.run_episode(tasks2[0], "static_star", 10000)
    
    assert result1.tokens_used == result2.tokens_used, "Same seed should produce same token usage"