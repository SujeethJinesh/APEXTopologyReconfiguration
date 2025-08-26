"""Evaluation harness for Success@Budget metric."""

from __future__ import annotations

import os
import random
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.eval.stubs.topology_switch import TopologySwitch

from .providers.swe_lite import SWELiteProvider, SWERecord
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
        split: str = "dev",
        limit: Optional[int] = None,
        offline: bool = False,
        oracle_smoke: bool = False,
    ):
        """Initialize harness.

        Args:
            mode: "stub" for fast CI testing, "swe" for SWE-bench Lite
            seed: Random seed for reproducibility
            split: Dataset split for SWE mode ("dev" or "test")
            limit: Optional limit on number of tasks
            offline: If True, only use local cache (no network)
            oracle_smoke: If True, apply gold patch for validation
        """
        self.mode = mode
        self.seed = seed
        self.split = split
        self.limit = limit
        self.offline = offline
        self.oracle_smoke = oracle_smoke
        self.rng = random.Random(seed)  # Use instance RNG for determinism

        if mode not in ["stub", "swe"]:
            raise ValueError(f"Invalid mode: {mode}. Use 'stub' or 'swe'")

        # Network gating for SWE mode
        if mode == "swe" and not offline:
            if os.getenv("APEX_ALLOW_NETWORK") != "1":
                raise RuntimeError(
                    "SWE mode requires network access. "
                    "Set APEX_ALLOW_NETWORK=1 or use --offline with fixtures."
                )

        # Initialize provider for SWE mode
        if mode == "swe":
            cache_dir = Path.home() / ".cache" / "apex" / "swe_bench"
            self.provider = SWELiteProvider(cache_dir=str(cache_dir))
            self.work_root = Path(tempfile.mkdtemp(prefix="apex_swe_"))

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
            limit = n_episodes or self.limit
            swe_records = self.provider.load(split=self.split, limit=limit, offline=self.offline)

            # Convert SWERecords to Tasks
            tasks = []
            for record in swe_records:
                # Create Task with SWE metadata
                task = Task(
                    task_id=record.task_id,
                    description=record.problem_statement[:200],  # Truncate for display
                    expected_success=None,  # Will be determined by test execution
                    token_cost=0,  # Will be measured during execution
                    topology_preference="star",  # Default preference
                    metadata={
                        "swe_record": record,  # Store full record for execution
                        "repo": record.repo,
                        "base_commit": record.base_commit[:8],
                    },
                )
                tasks.append(task)
            return tasks
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

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

        # Handle SWE mode differently
        if self.mode == "swe":
            # Run actual SWE-bench task
            if "swe_record" not in task.metadata:
                raise ValueError(f"Task {task.task_id} missing SWE record in metadata")

            swe_record = task.metadata["swe_record"]
            success, tokens_used = self._run_swe_episode(swe_record, budget)

            # For SWE mode, success is determined by test execution
            task.expected_success = success
        else:
            # Simulate task execution based on policy (stub mode)
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
            notes=f"mode={self.mode},topology_pref={task.topology_preference}",
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

    def _run_swe_episode(self, record: SWERecord, budget_tokens: int) -> Tuple[bool, int]:
        """Run a SWE-bench episode with actual repository and tests.

        Args:
            record: SWERecord with task details
            budget_tokens: Token budget for this episode

        Returns:
            (success, tokens_used) tuple
        """
        try:
            # Prepare workspace with repository at base commit
            repo_path = RepoManager.prepare_workspace(
                record=record,
                work_root=str(self.work_root),
                oracle=self.oracle_smoke,  # Apply gold patch in oracle mode
            )

            # Run tests - prioritize FAIL_TO_PASS tests
            test_result = RepoManager.run_tests(
                repo_path=repo_path,
                test_select=record.fail_to_pass if record.fail_to_pass else None,
                timeout_s=180,
            )

            # Check success: all selected tests must pass
            success = test_result["exit_code"] == 0 and test_result["failed"] == 0

            # Simulate token usage based on test execution time
            # Rough heuristic: 100 tokens per second of execution
            tokens_used = int(test_result["duration_s"] * 100)

            # Add base cost for repository setup
            tokens_used += 1000

            return success, tokens_used

        except Exception as e:
            # Log error and treat as failure
            print(f"Error in SWE episode {record.task_id}: {e}")
            return False, budget_tokens  # Use full budget on error

    def cleanup(self):
        """Clean up workspace after evaluation."""
        if hasattr(self, "work_root") and self.work_root.exists():
            RepoManager.cleanup_workspace(str(self.work_root))
