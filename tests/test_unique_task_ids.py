"""Test that task IDs are unique when n_episodes > base set."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from apex.eval.harness import EvalHarness, StubTask


def test_unique_task_ids_with_repetition():
    """Test that task IDs are unique when repeating base set."""
    
    harness = EvalHarness(mode="stub", seed=42)
    
    # Base set has 12 tasks
    base_tasks = StubTask.generate_stub_tasks(42)
    assert len(base_tasks) == 12
    
    # Request more episodes than base set
    n_episodes = 25
    tasks = harness.load_tasks(n_episodes=n_episodes)
    
    # Should have exactly n_episodes tasks
    assert len(tasks) == n_episodes, f"Expected {n_episodes} tasks, got {len(tasks)}"
    
    # All task IDs should be unique
    task_ids = [task.task_id for task in tasks]
    unique_ids = set(task_ids)
    assert len(unique_ids) == n_episodes, f"Found duplicate task IDs: {len(unique_ids)} unique out of {n_episodes}"
    
    # First 12 should have __rep_0 suffix
    for i in range(12):
        expected_id = f"{base_tasks[i].task_id}__rep_0"
        assert tasks[i].task_id == expected_id, f"Task {i}: expected {expected_id}, got {tasks[i].task_id}"
    
    # Next batch should have __rep_1 suffix
    for i in range(12, min(24, n_episodes)):
        base_idx = i - 12
        expected_id = f"{base_tasks[base_idx].task_id}__rep_1"
        assert tasks[i].task_id == expected_id, f"Task {i}: expected {expected_id}, got {tasks[i].task_id}"
    
    print(f"✓ All {n_episodes} task IDs are unique")
    print(f"  First 12: {task_ids[:12]}")
    print(f"  Repeated: {task_ids[12:15]}...")


def test_paired_bootstrap_uses_all_episodes():
    """Test that paired bootstrap uses all n_episodes."""
    
    harness = EvalHarness(mode="stub", seed=42)
    n_episodes = 20  # More than base 12
    
    # Generate episodes for two policies
    tasks = harness.load_tasks(n_episodes=n_episodes)
    
    apex_results = []
    static_results = []
    
    for task in tasks:
        apex_result = harness.run_episode(task, "bandit_v1", 10000)
        static_result = harness.run_episode(task, "static_star", 10000)
        
        apex_results.append(apex_result.to_dict())
        static_results.append(static_result.to_dict())
    
    # Save to JSONL
    with tempfile.TemporaryDirectory() as tmpdir:
        apex_path = Path(tmpdir) / "apex.jsonl"
        static_path = Path(tmpdir) / "static.jsonl"
        
        with open(apex_path, "w") as f:
            for r in apex_results:
                json.dump(r, f)
                f.write("\n")
        
        with open(static_path, "w") as f:
            for r in static_results:
                json.dump(r, f)
                f.write("\n")
        
        # Verify files have n_episodes lines
        with open(apex_path) as f:
            apex_lines = f.readlines()
        with open(static_path) as f:
            static_lines = f.readlines()
        
        assert len(apex_lines) == n_episodes
        assert len(static_lines) == n_episodes
        
        # All task IDs should be unique in each file
        apex_ids = set()
        static_ids = set()
        
        for line in apex_lines:
            obj = json.loads(line)
            apex_ids.add(obj["task_id"])
        
        for line in static_lines:
            obj = json.loads(line)
            static_ids.add(obj["task_id"])
        
        assert len(apex_ids) == n_episodes, f"APEX has {len(apex_ids)} unique IDs, expected {n_episodes}"
        assert len(static_ids) == n_episodes, f"Static has {len(static_ids)} unique IDs, expected {n_episodes}"
        
        print(f"✓ Both JSONL files have {n_episodes} unique task IDs")
        print(f"  APEX unique IDs: {len(apex_ids)}")
        print(f"  Static unique IDs: {len(static_ids)}")


if __name__ == "__main__":
    test_unique_task_ids_with_repetition()
    print()
    test_paired_bootstrap_uses_all_episodes()