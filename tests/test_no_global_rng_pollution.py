"""Test that harness doesn't pollute global RNG state."""

from __future__ import annotations

import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.eval.harness import EvalHarness, StubTask


def test_no_global_rng_pollution():
    """Verify that harness operations don't affect global RNG."""
    
    # Set global RNG to known state
    random.seed(999)
    expected_values = [random.random() for _ in range(5)]
    
    # Reset and create harnesses with different seeds
    random.seed(999)
    
    # Create harness 1
    harness1 = EvalHarness(mode="stub", seed=42)
    tasks1 = harness1.load_tasks(n_episodes=5)
    
    # Create harness 2 with different seed
    harness2 = EvalHarness(mode="stub", seed=123)
    tasks2 = harness2.load_tasks(n_episodes=5)
    
    # Run episodes
    for task in tasks1:
        harness1.run_episode(task, "static_star", 10000)
    
    for task in tasks2:
        harness2.run_episode(task, "static_chain", 10000)
    
    # Generate stub tasks (should not affect global RNG)
    StubTask.generate_stub_tasks(seed=777)
    StubTask.generate_stub_tasks(seed=888)
    
    # Check global RNG still produces expected values
    actual_values = [random.random() for _ in range(5)]
    
    assert actual_values == expected_values, "Global RNG state was polluted"
    print("✓ No global RNG pollution detected")
    print(f"  Expected: {expected_values[:3]}...")
    print(f"  Actual:   {actual_values[:3]}...")


def test_independent_harness_determinism():
    """Test that harnesses with different seeds are independent."""
    
    harness1 = EvalHarness(mode="stub", seed=42)
    harness2 = EvalHarness(mode="stub", seed=42)  # Same seed
    harness3 = EvalHarness(mode="stub", seed=123)  # Different seed
    
    tasks = StubTask.generate_stub_tasks(seed=1)
    
    # Run same task through each harness
    result1 = harness1.run_episode(tasks[0], "static_star", 10000)
    result2 = harness2.run_episode(tasks[0], "static_star", 10000)
    result3 = harness3.run_episode(tasks[0], "static_star", 10000)
    
    # Same seed should give same results
    assert result1.tokens_used == result2.tokens_used, "Same seed should be deterministic"
    
    # Different seed should give different results (with high probability)
    assert result1.tokens_used != result3.tokens_used, "Different seeds should differ"
    
    print("✓ Harnesses are independent and deterministic")
    print(f"  Seed 42:  {result1.tokens_used} tokens")
    print(f"  Seed 42:  {result2.tokens_used} tokens (same)")
    print(f"  Seed 123: {result3.tokens_used} tokens (different)")


if __name__ == "__main__":
    test_no_global_rng_pollution()
    print()
    test_independent_harness_determinism()