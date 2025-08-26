"""Test the evaluation harness with stub mode."""

from __future__ import annotations

import json

import pytest

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.eval.harness import EvalHarness, StubTask
from apex.eval.stubs.topology_switch import TopologySwitch


class TestStubHarness:
    """Test stub harness functionality."""

    def test_stub_task_generation(self):
        """Test that stub tasks are generated deterministically."""
        tasks1 = StubTask.generate_stub_tasks(seed=42)
        tasks2 = StubTask.generate_stub_tasks(seed=42)

        assert len(tasks1) == 12
        assert len(tasks2) == 12

        # Should be deterministic with same seed
        for t1, t2 in zip(tasks1, tasks2):
            assert t1.task_id == t2.task_id
            assert t1.token_cost == t2.token_cost
            assert t1.expected_success == t2.expected_success

    def test_harness_initialization(self):
        """Test harness initialization."""
        harness = EvalHarness(mode="stub", seed=42)
        assert harness.mode == "stub"
        assert harness.seed == 42

        # SWE mode should raise in CI
        with pytest.raises(NotImplementedError):
            EvalHarness(mode="swe")

    def test_budget_enforcement(self):
        """Test that budget logic is enforced correctly."""
        harness = EvalHarness(mode="stub", seed=42)
        tasks = harness.load_tasks(n_episodes=3)

        # Run with tight budget that some tasks will exceed
        budget = 5000

        for task in tasks:
            result = harness.run_episode(task=task, policy="static_star", budget=budget)

            # If tokens exceed budget, must be marked as over_budget
            if result.tokens_used > budget:
                assert result.over_budget is True
                assert result.success is False  # Can't succeed if over budget
            else:
                assert result.over_budget is False
                # Success depends on task's expected_success
                if task.expected_success:
                    assert result.success is True

    def test_all_policies_output(self):
        """Test that all policies produce valid output."""
        harness = EvalHarness(mode="stub", seed=42)
        tasks = harness.load_tasks(n_episodes=12)

        policies = ["static_star", "static_chain", "static_flat", "bandit_v1"]

        for policy in policies:
            # Setup switch and bandit for dynamic policy
            switch = None
            bandit = None
            if policy == "bandit_v1":
                switch = TopologySwitch(initial="star", seed=42)
                bandit = BanditSwitchV1(d=8, seed=42)

            results = []
            for task in tasks:
                result = harness.run_episode(
                    task=task, policy=policy, budget=10000, switch=switch, bandit=bandit
                )
                results.append(result)

            # Verify all results have required fields
            for result in results:
                assert result.task_id is not None
                assert result.policy == policy
                assert isinstance(result.success, bool)
                assert isinstance(result.tokens_used, int)
                assert isinstance(result.over_budget, bool)
                assert result.budget == 10000
                assert result.seed == 42

                # Dynamic policy should have epoch switches
                if policy == "bandit_v1":
                    assert result.epoch_switches >= 0

    def test_schema_validation(self):
        """Test that output schemas match spec."""
        harness = EvalHarness(mode="stub", seed=42)
        task = harness.load_tasks(n_episodes=1)[0]

        result = harness.run_episode(task=task, policy="static_star", budget=10000)

        # Convert to dict for JSON
        result_dict = result.to_dict()

        # Required fields
        required_fields = [
            "task_id",
            "policy",
            "success",
            "tokens_used",
            "over_budget",
            "budget",
            "seed",
            "epoch_switches",
        ]

        for field in required_fields:
            assert field in result_dict

        # Verify JSON serializable
        json_str = json.dumps(result_dict)
        reloaded = json.loads(json_str)
        assert reloaded == result_dict

    def test_deterministic_execution(self):
        """Test that execution is deterministic with same seed."""
        harness1 = EvalHarness(mode="stub", seed=42)
        harness2 = EvalHarness(mode="stub", seed=42)

        tasks1 = harness1.load_tasks(n_episodes=5)
        tasks2 = harness2.load_tasks(n_episodes=5)

        for t1, t2 in zip(tasks1, tasks2):
            r1 = harness1.run_episode(t1, "static_star", 10000)
            r2 = harness2.run_episode(t2, "static_star", 10000)

            assert r1.tokens_used == r2.tokens_used
            assert r1.success == r2.success
            assert r1.over_budget == r2.over_budget
