"""Evaluation harness for Success@Budget metric."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.runtime.topology_switch import TopologySwitch

from .task import Task, TaskResult


class StubTask:
    """Stub task generator for fast deterministic testing."""

    @staticmethod
    def generate_stub_tasks(seed: int = 42) -> List[Task]:
        """Generate deterministic stub tasks for testing.

        Each task simulates different token costs and success patterns
        across different topologies to ensure variance.
        """
        random.seed(seed)

        tasks = [
            # Lightweight planner tasks (prefer star)
            Task("stub_plan_1", "Simple planning task", True, 2500, "star"),
            Task("stub_plan_2", "Complex planning task", True, 4800, "star"),
            Task("stub_plan_3", "Failed planning task", False, 3200, "star"),
            # Chain tasks (prefer chain)
            Task("stub_chain_1", "Sequential processing", True, 5500, "chain"),
            Task("stub_chain_2", "Multi-step pipeline", True, 7200, "chain"),
            Task("stub_chain_3", "Failed chain task", False, 6000, "chain"),
            # Heavy compute tasks (prefer flat)
            Task("stub_compute_1", "Parallel computation", True, 8500, "flat"),
            Task("stub_compute_2", "Distributed work", True, 9800, "flat"),
            Task("stub_compute_3", "Failed compute task", False, 9000, "flat"),
            # Mixed tasks to test switching
            Task("stub_mixed_1", "Adaptive workload", True, 6500, "chain"),
            Task("stub_mixed_2", "Variable workload", True, 7500, "star"),
            Task("stub_mixed_3", "Failed mixed task", False, 10500, "flat"),
        ]

        return tasks


class EvalHarness:
    """Main evaluation harness for Success@Budget metric."""

    def __init__(self, mode: str = "stub", seed: int = 42):
        """Initialize harness.

        Args:
            mode: "stub" for fast CI testing, "swe" for SWE-bench Lite
            seed: Random seed for reproducibility
        """
        self.mode = mode
        self.seed = seed
        self.rng = random.Random(seed)  # Use instance RNG for determinism

        if mode not in ["stub", "swe"]:
            raise ValueError(f"Invalid mode: {mode}. Use 'stub' or 'swe'")

        if mode == "swe":
            raise NotImplementedError(
                "SWE-bench mode not enabled in CI. Set environment flag to enable."
            )

    def load_tasks(self, n_episodes: Optional[int] = None) -> List[Task]:
        """Load tasks based on mode."""
        if self.mode == "stub":
            tasks = StubTask.generate_stub_tasks(self.seed)
            if n_episodes:
                # Repeat tasks if needed to reach n_episodes
                while len(tasks) < n_episodes:
                    tasks.extend(StubTask.generate_stub_tasks(self.seed + len(tasks)))
                tasks = tasks[:n_episodes]
            return tasks
        else:
            raise NotImplementedError(f"Mode {self.mode} not implemented")

    def run_episode(
        self,
        task: Task,
        policy: str,
        budget: int,
        switch: Optional[TopologySwitch] = None,
        bandit: Optional[BanditSwitchV1] = None,
    ) -> TaskResult:
        """Run a single episode with budget enforcement.

        Args:
            task: Task to execute
            policy: Policy name (static_star, static_chain, static_flat, bandit_v1)
            budget: Token budget for this episode
            switch: Optional switch for dynamic policies
            bandit: Optional bandit for dynamic policies

        Returns:
            TaskResult with success/failure and token usage
        """
        epoch_switches = 0

        # Simulate task execution based on policy
        if policy.startswith("static_"):
            topology = policy.replace("static_", "")
            tokens_used = self._simulate_static_execution(task, topology)
        elif policy == "bandit_v1":
            if switch is None:
                # Create default switch for bandit
                switch = TopologySwitch(initial="star", seed=self.seed)
            if bandit is None:
                bandit = BanditSwitchV1(d=8, seed=self.seed)
            tokens_used, epoch_switches = self._simulate_dynamic_execution(task, switch, bandit)
        else:
            raise ValueError(f"Unknown policy: {policy}")

        # Check budget violation
        over_budget = tokens_used > budget

        # Success@Budget: task succeeds only if completed AND under budget
        success = task.expected_success and not over_budget

        return TaskResult(
            task_id=task.task_id,
            policy=policy,
            success=success,
            tokens_used=tokens_used,
            over_budget=over_budget,
            budget=budget,
            seed=self.seed,
            epoch_switches=epoch_switches,
            notes=f"topology_pref={task.topology_preference}",
        )

    def _simulate_static_execution(self, task: Task, topology: str) -> int:
        """Simulate execution with static topology.

        Returns token cost based on topology match.
        """
        base_cost = task.token_cost

        # Add penalty if topology doesn't match preference
        if topology != task.topology_preference:
            # Wrong topology adds 15-25% overhead
            penalty = self.rng.uniform(0.15, 0.25)
            base_cost = int(base_cost * (1 + penalty))

        # Add small random variance (±5%)
        variance = self.rng.uniform(-0.05, 0.05)
        final_cost = int(base_cost * (1 + variance))

        return final_cost

    def _simulate_dynamic_execution(
        self, task: Task, switch: TopologySwitch, bandit: BanditSwitchV1
    ) -> Tuple[int, int]:
        """Simulate execution with dynamic topology switching.

        Returns (tokens_used, epoch_switches).
        """
        # Simulate multiple steps with potential switches
        total_tokens = 0
        epoch_switches = 0
        steps = self.rng.randint(3, 7)  # Variable number of steps

        for step in range(steps):
            # Get current topology
            active_topo = switch.active()

            # Compute step cost based on topology match
            step_ratio = (step + 1) / steps
            step_cost = int(task.token_cost * step_ratio / steps)

            if active_topo.topology != task.topology_preference:
                # Wrong topology adds overhead
                penalty = self.rng.uniform(0.10, 0.20)
                step_cost = int(step_cost * (1 + penalty))

            total_tokens += step_cost

            # Simulate bandit update and potential switch
            if step < steps - 1:  # Don't switch on last step
                # Simulate reward signal
                reward = 1.0 if active_topo.topology == task.topology_preference else 0.3

                # Bandit may switch based on reward
                old_epoch = active_topo.epoch

                # Create simple feature vector for bandit
                x = [0.5] * 8  # Simple 8-feature vector
                action = bandit.decide(x)["action"]
                bandit.update(x, action, reward)

                # Apply action to switch if needed
                # Match ACTION_MAP from bandit_v1.py: {0: "stay", 1: "star", 2: "chain", 3: "flat"}
                action_map = {0: "stay", 1: "star", 2: "chain", 3: "flat"}
                if action != 0:  # Not "stay"
                    switch.commit(action_map[action])

                new_topo = switch.active()

                if new_topo.epoch != old_epoch:
                    epoch_switches += 1

        # Dynamic policy can achieve 5-10% savings when it adapts well
        if epoch_switches > 0:
            savings = self.rng.uniform(0.05, 0.10)
            total_tokens = int(total_tokens * (1 - savings))

        return total_tokens, epoch_switches
