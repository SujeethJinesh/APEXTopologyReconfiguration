"""Test unique task ID generation when repeating tasks."""

from apex.eval.harness import EvalHarness, StubTask


def test_unique_task_ids_with_repetition():
    """Verify unique task_id per episode when repeating base tasks."""
    h = EvalHarness(mode="stub", seed=1)

    base = StubTask.generate_stub_tasks()
    n_base = len(base)

    # Force repetition beyond 2x to see multiple suffixes
    n = n_base * 2 + 3
    tasks = h.load_tasks(n)

    ids = [t.task_id for t in tasks]
    assert len(ids) == n, f"Expected {n} tasks, got {len(ids)}"
    assert len(set(ids)) == n, "Expected unique task_id per episode when repeating"

    # First batch should have original IDs (no suffix)
    for i in range(n_base):
        assert "__rep_" not in ids[i], f"First batch should not have suffix: {ids[i]}"

    # Second batch should have __rep_1 suffix
    for i in range(n_base, min(2 * n_base, n)):
        assert "__rep_1" in ids[i], f"Second batch should have __rep_1 suffix: {ids[i]}"

    # Third partial batch should have __rep_2 suffix
    if n > 2 * n_base:
        for i in range(2 * n_base, n):
            assert "__rep_2" in ids[i], f"Third batch should have __rep_2 suffix: {ids[i]}"


def test_paired_bootstrap_validity():
    """Verify task IDs enable valid paired bootstrap across policies."""
    # Create two harnesses (could be different policies)
    h1 = EvalHarness(mode="stub", seed=42)
    h2 = EvalHarness(mode="stub", seed=42)

    # Load same number of episodes (with repetition)
    n_episodes = 25
    tasks1 = h1.load_tasks(n_episodes)
    tasks2 = h2.load_tasks(n_episodes)

    # Task IDs must match exactly for pairing
    ids1 = [t.task_id for t in tasks1]
    ids2 = [t.task_id for t in tasks2]

    assert ids1 == ids2, "Task IDs must match across policies for paired bootstrap"

    # Verify suffixes are consistent
    base_count = len(StubTask.generate_stub_tasks())
    expected_reps = (n_episodes + base_count - 1) // base_count

    for rep in range(expected_reps):
        if rep == 0:
            # First repetition has no suffix
            for i in range(min(base_count, n_episodes)):
                assert "__rep_" not in ids1[i], f"First rep should not have suffix: {ids1[i]}"
        else:
            # Subsequent repetitions have __rep_N suffix
            start = rep * base_count
            end = min(start + base_count, n_episodes)
            for i in range(start, end):
                assert f"__rep_{rep}" in ids1[i], f"Rep {rep} should have suffix: {ids1[i]}"


def test_no_task_id_collision():
    """Ensure no task ID collisions even with many repetitions."""
    h = EvalHarness(mode="stub", seed=99)

    # Load many episodes (10x base set)
    base_count = len(StubTask.generate_stub_tasks())
    n_episodes = base_count * 10
    tasks = h.load_tasks(n_episodes)

    # All task IDs must be unique
    ids = [t.task_id for t in tasks]
    assert len(ids) == n_episodes
    assert len(set(ids)) == n_episodes, f"Found duplicate task IDs in {n_episodes} episodes"

    # Verify suffix pattern
    for i, task_id in enumerate(ids):
        rep = i // base_count
        if rep == 0:
            assert "__rep_" not in task_id
        else:
            assert f"__rep_{rep}" in task_id, f"Wrong suffix at index {i}: {task_id}"
