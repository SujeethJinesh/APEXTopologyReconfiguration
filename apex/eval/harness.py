"""Evaluation harness for Success@Budget metric."""

from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.eval.stubs.topology_switch import TopologySwitch

from .providers import SWELiteProvider
from .repo_manager import RepoManager
from .task import Task, TaskResult


class StubTask:
    """Stub task generator for fast deterministic testing."""

    @staticmethod
    def generate_stub_tasks() -> List[Task]:
        """Generate deterministic stub tasks for testing.

        Each task simulates different token costs and success patterns
        across different topologies to ensure variance.

        Note: In stub mode, 'expected_success' is a predetermined property
        rather than an observed outcome. Real completion will be determined
        by actual task execution in SWE-bench mode.

        IMPORTANT: Do not mutate the process-global RNG here.
        """
        # No RNG seeding - task list is fully deterministic

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

    def __init__(
        self,
        mode: str = "stub",
        seed: int = 42,
        split: Optional[Literal["dev", "test"]] = None,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize harness.

        Args:
            mode: "stub" for fast CI testing, "swe" for SWE-bench Lite
            seed: Random seed for reproducibility
            split: Dataset split for SWE mode ("dev" or "test")
            cache_dir: Cache directory for SWE datasets
        """
        self.mode = mode
        self.seed = seed
        self.rng = random.Random(seed)  # Use instance RNG for determinism

        if mode not in ["stub", "swe"]:
            raise ValueError(f"Invalid mode: {mode}. Use 'stub' or 'swe'")

        if mode == "swe":
            if not os.getenv("APEX_ALLOW_NETWORK"):
                raise NotImplementedError(
                    "SWE-bench mode requires network access. Set APEX_ALLOW_NETWORK=1 to enable."
                )
            if split is None:
                raise ValueError("split required for SWE mode (dev or test)")
            if cache_dir is None:
                cache_dir = Path("~/.cache/apex/swe_bench").expanduser()

            self.split = split
            self.cache_dir = cache_dir
            self.work_dir = Path.cwd() / "work" / "swe_bench"
            self.repo_manager = RepoManager(self.work_dir)

    def load_tasks(self, n_episodes: Optional[int] = None) -> List[Task]:
        """Load tasks based on mode."""
        if self.mode == "stub":
            base_tasks = StubTask.generate_stub_tasks()
            if n_episodes and n_episodes > len(base_tasks):
                # Extend with uniquely suffixed task IDs
                tasks = []
                rep = 0
                while len(tasks) < n_episodes:
                    for task in base_tasks:
                        if len(tasks) >= n_episodes:
                            break
                        # Ensure per-episode unique identifiers when repeating the base set
                        new_id = task.task_id if rep == 0 else f"{task.task_id}__rep_{rep}"
                        unique_task = Task(
                            task_id=new_id,
                            description=task.description,
                            expected_success=task.expected_success,
                            token_cost=task.token_cost,
                            topology_preference=task.topology_preference,
                            metadata=task.metadata,
                        )
                        tasks.append(unique_task)
                    rep += 1
                return tasks[:n_episodes]
            else:
                return base_tasks[:n_episodes] if n_episodes else base_tasks
        elif self.mode == "swe":
            # Load SWE-bench Lite tasks
            provider = SWELiteProvider(self.split, self.cache_dir, limit=n_episodes)
            tasks = []
            for eval_task in provider:
                # Convert EvalTask to Task for compatibility
                # Note: SWE tasks don't have predetermined success or preferences
                task = Task(
                    task_id=eval_task.task_id,
                    description=eval_task.problem[:200],  # Truncate for Task
                    expected_success=False,  # Will be determined by test execution
                    token_cost=0,  # Will be tracked during execution
                    topology_preference=None,  # No preference for SWE tasks
                    metadata={
                        "repo": eval_task.repo,
                        "commit": eval_task.base_commit,
                        "test_patch": eval_task.test_patch,
                        "patch": eval_task.patch,
                        "hints": eval_task.hints,
                    },
                )
                tasks.append(task)
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
            policy: Policy name (static_star, static_chain, static_flat, apex_dynamic)
            budget: Token budget for this episode
            switch: Optional switch for dynamic policies
            bandit: Optional bandit for dynamic policies

        Returns:
            TaskResult with success/failure and token usage
        """
        if self.mode == "swe":
            return self._run_swe_episode(task, policy, budget, switch, bandit)

        # Stub mode execution
        epoch_switches = 0

        # Simulate task execution based on policy
        if policy.startswith("static_"):
            topology = policy.replace("static_", "")
            tokens_used = self._simulate_static_execution(task, topology)
        elif policy in ["bandit_v1", "apex_dynamic"]:
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

    def _run_swe_episode(
        self,
        task: Task,
        policy: str,
        budget: int,
        switch: Optional[TopologySwitch] = None,
        bandit: Optional[BanditSwitchV1] = None,
    ) -> TaskResult:
        """Run SWE-bench episode with real repository checkout and test execution.

        Args:
            task: Task containing SWE-bench metadata
            policy: Policy name
            budget: Token budget (10k default)
            switch: Optional switch for dynamic policies
            bandit: Optional bandit for dynamic policies

        Returns:
            TaskResult with test execution results
        """
        start_time = time.time()
        metadata = task.metadata
        repo = metadata["repo"]
        commit = metadata["commit"]
        test_patch = metadata["test_patch"]

        # Track execution details
        topology_trace = []
        switches = 0
        budget_denied = 0

        # Prepare repository checkout
        try:
            repo_path = self.repo_manager.prepare_checkout(repo, commit)
        except Exception as e:
            # Repository preparation failed
            return TaskResult(
                task_id=task.task_id,
                policy=policy,
                success=False,
                tokens_used=0,
                over_budget=False,
                budget=budget,
                seed=self.seed,
                epoch_switches=0,
                notes=f"repo_setup_failed: {e}",
            )

        # Apply test patch
        patch_applied = self.repo_manager.apply_patch(repo_path, test_patch, "test")
        if not patch_applied:
            # Test patch failed to apply
            return TaskResult(
                task_id=task.task_id,
                policy=policy,
                success=False,
                tokens_used=0,
                over_budget=False,
                budget=budget,
                seed=self.seed,
                epoch_switches=0,
                notes="test_patch_apply_failed",
            )

        # Simulate agent execution with topology switching
        # For MVP, we'll use a simple token counter
        tokens_used = 0

        if policy.startswith("static_"):
            topology = policy.replace("static_", "")
            # Simulate static execution
            tokens_used = self.rng.randint(3000, 9000)  # Random cost for MVP
            topology_trace.append({"tick": 0, "topo": topology, "dwell": 1, "cooldown": 0})

        elif policy == "apex_dynamic":
            if switch is None:
                switch = TopologySwitch(initial="star", seed=self.seed)
            if bandit is None:
                bandit = BanditSwitchV1(d=8, seed=self.seed)

            # Simulate dynamic execution with switches
            steps = self.rng.randint(3, 7)
            for step in range(steps):
                active = switch.active()
                topology_trace.append(
                    {
                        "tick": step,
                        "topo": active.topology,
                        "dwell": active.dwell,
                        "cooldown": active.cooldown,
                    }
                )

                # Simulate token usage
                step_tokens = self.rng.randint(1000, 2000)
                if tokens_used + step_tokens > budget:
                    budget_denied += 1
                    break
                tokens_used += step_tokens

                # Maybe switch topology
                if step < steps - 1:
                    x = [self.rng.random() for _ in range(8)]
                    action = bandit.decide(x)["action"]
                    reward = self.rng.random()
                    bandit.update(x, action, reward)

                    action_map = {0: "stay", 1: "star", 2: "chain", 3: "flat"}
                    if action != 0:
                        old_epoch = active.epoch
                        switch.commit(action_map[action])
                        if switch.active().epoch != old_epoch:
                            switches += 1

        # Run tests to determine success
        test_success, test_output = self.repo_manager.run_tests(repo_path)

        # Check budget violation
        over_budget = tokens_used > budget

        # Success@Budget: tests pass AND under budget
        success = test_success and not over_budget

        episode_ms = (time.time() - start_time) * 1000

        # Return extended result for SWE mode
        result = TaskResult(
            task_id=task.task_id,
            policy=policy,
            success=success,
            tokens_used=tokens_used,
            over_budget=over_budget,
            budget=budget,
            seed=self.seed,
            epoch_switches=switches,
            notes=f"swe_mode,tests_{'passed' if test_success else 'failed'}",
        )

        # Add SWE-specific fields to metadata
        result.metadata = {
            "budget_denied": budget_denied,
            "topology_trace": topology_trace,
            "switches": switches,
            "episode_ms": episode_ms,
        }

        return result
