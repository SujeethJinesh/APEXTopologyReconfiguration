"""Evaluation harness for Success@Budget metric."""

from __future__ import annotations

import logging
import os
import random
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

from apex.agents.message_swe_agent import MessageSWEAgent

# APEX system components for dynamic topology switching
from apex.controllers.apex_controller import APEXController
from apex.runtime.coordinator import Coordinator
from apex.runtime.message import AgentID
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine

from .providers.swe_lite import SWELiteProvider, SWERecord
from .repo_manager import RepoManager
from .task import Task, TaskResult

# StubTask class removed - only real SWE-bench tasks allowed


class EvalHarness:
    """Main evaluation harness for Success@Budget metric."""

    def __init__(
        self,
        seed: int = 42,
        split: str = "dev",
        limit: Optional[int] = None,
        offline: bool = False,
        oracle_smoke: bool = False,
        task_list: Optional[List[str]] = None,
    ):
        """Initialize harness for REAL SWE-bench evaluation only.

        Args:
            seed: Random seed for reproducibility
            split: Dataset split ("dev" or "test")
            limit: Optional limit on number of tasks
            offline: If True, only use local cache (no network)
            oracle_smoke: If True, apply gold patch for validation
            task_list: Optional list of task IDs to use (ensures consistent evaluation)
        """
        # Configure logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(f"{__name__}.EvalHarness")

        # ONLY real SWE-bench mode allowed
        self.seed = seed
        self.split = split
        self.limit = limit
        self.offline = offline
        self.oracle_smoke = oracle_smoke
        self.task_list = task_list
        self.rng = random.Random(seed)  # Use instance RNG for determinism

        self.logger.info(
            f"[EVAL] Initializing harness: seed={seed}, split={split}, "
            f"limit={limit}, offline={offline}, oracle={oracle_smoke}"
        )

        # Network gating for SWE mode
        if not offline:
            if os.getenv("APEX_ALLOW_NETWORK") != "1":
                self.logger.error("[EVAL] Network access denied - APEX_ALLOW_NETWORK not set")
                raise RuntimeError(
                    "SWE mode requires network access. "
                    "Set APEX_ALLOW_NETWORK=1 or use --offline with fixtures."
                )
            self.logger.info("[EVAL] Network access enabled for task loading")

        # Always initialize SWE provider (no stub mode)
        cache_dir = Path.home() / ".cache" / "apex" / "swe_bench"
        self.logger.info(f"[EVAL] SWE provider cache: {cache_dir}")
        self.provider = SWELiteProvider(cache_dir=str(cache_dir))
        # Use temp directory that will be cleaned up
        self.work_root = Path(tempfile.mkdtemp(prefix="apex_swe_"))
        self.logger.info(f"[EVAL] Work directory: {self.work_root}")

    def load_tasks(self, n_episodes: Optional[int] = None) -> List[Task]:
        """Load REAL SWE-bench tasks only."""
        # ONLY real SWE-bench tasks - no simulation allowed
        start_time = time.time()
        self.logger.info(
            f"[EVAL] Loading tasks: n_episodes={n_episodes}, task_list={self.task_list}"
        )

        # When task_list is provided, we need to load from ALL splits to find tasks
        # This handles the case where we use test split IDs but run with --split dev
        if self.task_list:
            # Load both splits to find all task IDs
            all_task_map = {}

            # Try test split first (300 tasks)
            try:
                self.logger.info("[EVAL] Loading test split for task lookup")
                test_records = self.provider.load(split="test", limit=None, offline=self.offline)
                self.logger.info(f"[EVAL] Found {len(test_records)} tasks in test split")
                for record in test_records:
                    task = Task(
                        task_id=record.task_id,
                        description=record.problem_statement[:200],
                        expected_success=None,
                        token_cost=0,
                        topology_preference="star",
                        metadata={
                            "swe_record": record,
                            "repo": record.repo,
                            "base_commit": record.base_commit[:8],
                        },
                    )
                    all_task_map[record.task_id] = task
            except Exception as e:
                self.logger.warning(f"[EVAL] Could not load test split: {e}")

            # Also try dev split (23 tasks)
            try:
                self.logger.info("[EVAL] Loading dev split for task lookup")
                dev_records = self.provider.load(split="dev", limit=None, offline=self.offline)
                self.logger.info(f"[EVAL] Found {len(dev_records)} tasks in dev split")
                for record in dev_records:
                    task = Task(
                        task_id=record.task_id,
                        description=record.problem_statement[:200],
                        expected_success=None,
                        token_cost=0,
                        topology_preference="star",
                        metadata={
                            "swe_record": record,
                            "repo": record.repo,
                            "base_commit": record.base_commit[:8],
                        },
                    )
                    all_task_map[record.task_id] = task
            except Exception as e:
                self.logger.warning(f"[EVAL] Could not load dev split: {e}")

            # Filter by task_list
            filtered_tasks = []
            for task_id in self.task_list:
                if task_id in all_task_map:
                    filtered_tasks.append(all_task_map[task_id])
                    self.logger.debug(f"[EVAL] Found task {task_id} in splits")
                else:
                    self.logger.warning(f"[EVAL] Task {task_id} not found in any SWE split")

            load_time = time.time() - start_time
            self.logger.info(
                f"[EVAL] Task loading completed: {len(filtered_tasks)} tasks in {load_time:.2f}s"
            )
            return filtered_tasks

        # Original behavior when no task_list provided
        limit = n_episodes or self.limit
        self.logger.info(f"[EVAL] Loading {self.split} split: limit={limit}")
        swe_records = self.provider.load(split=self.split, limit=limit, offline=self.offline)
        self.logger.info(f"[EVAL] Loaded {len(swe_records)} SWE records")

        # Convert SWERecords to Tasks
        all_tasks = []
        task_map = {}
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
            all_tasks.append(task)
            task_map[record.task_id] = task

        load_time = time.time() - start_time
        self.logger.info(
            f"[EVAL] Task conversion completed: {len(all_tasks)} tasks in {load_time:.2f}s"
        )
        return all_tasks

    def run_episode(
        self,
        task: Task,
        policy: str,
        budget: int,
        switch: Optional[Any] = None,
        bandit: Optional[Any] = None,  # BanditSwitchV1
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
        episode_start = time.time()
        self.logger.info(
            f"[EVAL] Starting episode: task={task.task_id}, policy={policy}, budget={budget}"
        )

        epoch_switches = 0

        # Run actual SWE-bench task - NO SIMULATION
        if "swe_record" not in task.metadata:
            self.logger.error(f"[EVAL] Task {task.task_id} missing SWE record metadata")
            raise ValueError(f"Task {task.task_id} missing SWE record in metadata")

        swe_record = task.metadata["swe_record"]
        self.logger.info(
            f"[EVAL] Running SWE episode: repo={swe_record.repo}, "
            f"base_commit={swe_record.base_commit[:8]}"
        )

        # Check if this is the APEX dynamic topology policy
        if policy == "apex":
            self.logger.info("[EVAL] Using APEX dynamic topology policy with MessageSWEAgent")
            success, tokens_used, epoch_switches = self._run_apex_swe_episode(swe_record, budget)
        else:
            # Use existing static policy behavior
            # Convert async to sync for compatibility with existing code
            import asyncio

            import nest_asyncio
            nest_asyncio.apply()  # Allow nested event loops
            success, tokens_used = asyncio.run(self._run_swe_episode(swe_record, budget))

        # Success is determined by test execution
        task.expected_success = success

        # Check budget violation
        over_budget = tokens_used > budget
        episode_time = time.time() - episode_start

        self.logger.info(
            f"[EVAL] Episode completed: success={success}, tokens={tokens_used}/{budget}, "
            f"over_budget={over_budget}, time={episode_time:.2f}s"
        )

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

    async def _run_swe_episode(self, record: SWERecord, budget_tokens: int) -> Tuple[bool, int]:
        """Run a SWE-bench episode with actual repository and tests.

        Args:
            record: SWERecord with task details
            budget_tokens: Token budget for this episode

        Returns:
            (success, tokens_used) tuple
        """
        swe_start = time.time()
        self.logger.info(
            f"[EVAL] SWE episode start: task_id={record.task_id}, oracle={self.oracle_smoke}"
        )

        try:
            # Prepare workspace with repository at base commit
            repo_path = RepoManager.prepare_workspace(
                record=record,
                work_root=str(self.work_root),
                oracle=self.oracle_smoke,  # Apply gold patch in oracle mode
            )

            # If in oracle mode, just run tests (gold patch already applied)
            if self.oracle_smoke:
                self.logger.info("[EVAL] Oracle mode: running validation tests only")
                test_result = RepoManager.run_tests(
                    repo_path=repo_path,
                    test_select=record.fail_to_pass if record.fail_to_pass else None,
                    timeout_s=180,
                )
                success = test_result["exit_code"] == 0 and test_result["failed"] == 0
                tokens_used = int(test_result["duration_s"] * 100) + 1000
                self.logger.info(
                    f"[EVAL] Oracle result: success={success}, "
                    f"test_duration={test_result['duration_s']:.2f}s"
                )
                return success, tokens_used

            # Create LLM client for agent reasoning
            self.logger.info("[EVAL] Creating LLM client for agent reasoning")
            import os

            from apex.llm.client import LLMConfig, PortableLLMClient
            
            # Ensure LLM is enabled
            os.environ["APEX_ALLOW_LLM"] = "1"
            os.environ["APEX_ALLOW_NETWORK"] = "1"
            
            # Create LLM client with 3 instances
            llm_config = LLMConfig(num_instances=3, timeout_s=180)
            llm_client = PortableLLMClient(config=llm_config)
            
            # Start LLM instances
            await llm_client.ensure_started()
            
            # Create MessageSWEAgent for collaborative solving
            self.logger.info("[EVAL] Creating MessageSWEAgent for collaborative solving")
            from apex.agents.message_swe_agent import MessageSWEAgent
            from apex.integrations.mcp.fs_api import FS
            from apex.runtime.message import AgentID
            from apex.runtime.router import Router
            from apex.runtime.switch import SwitchEngine
            
            # Initialize router and switch for message passing
            router = Router()
            switch = SwitchEngine(router=router, quiesce_deadline_ms=50)
            
            # Create filesystem interface sandboxed to repo
            from apex.integrations.mcp.fs_local import LocalFS
            fs = LocalFS(base_path=Path(repo_path))
            
            # Create the message-based SWE agent
            message_agent = MessageSWEAgent(
                agent_id=AgentID("SWE-Coordinator"),
                router=router,
                switch=switch,
                fs=fs,
                episode_id=record.task_id,
                llm=llm_client
            )
            
            # Solve the task using collaborative agents
            self.logger.info(f"[EVAL] Starting collaborative solving for {record.task_id}")
            success, tokens_used = await message_agent.solve_task(
                problem_statement=record.problem_statement,
                repo_path=Path(repo_path),
                fail_tests=record.fail_to_pass if record.fail_to_pass else [],
                budget=budget_tokens
            )
            
            self.logger.info(f"[EVAL] Agent completed: success={success}, tokens={tokens_used}")
            
            # If agent claims success, verify with actual test run
            if success:
                self.logger.info("[EVAL] Agent claims success, verifying with tests")
                test_result = RepoManager.run_tests(
                    repo_path=repo_path,
                    test_select=record.fail_to_pass if record.fail_to_pass else None,
                    timeout_s=180,
                )
                success = test_result["exit_code"] == 0 and test_result["failed"] == 0
                self.logger.info(f"[EVAL] Test verification: {success}")
            
            return success, tokens_used

        except Exception as e:
            # Log error and treat as failure
            swe_time = time.time() - swe_start
            self.logger.error(
                f"[EVAL] SWE episode error: task={record.task_id}, error={e}, "
                f"time={swe_time:.2f}s"
            )
            return False, budget_tokens  # Use full budget on error

    def _run_apex_swe_episode(self, record: SWERecord, budget_tokens: int) -> Tuple[bool, int, int]:
        """Run a SWE-bench episode with APEX dynamic topology switching.

        Args:
            record: SWERecord with task details
            budget_tokens: Token budget for this episode

        Returns:
            (success, tokens_used, epoch_switches) tuple
        """
        import asyncio
        import uuid

        apex_start = time.time()
        self.logger.info(
            f"[EVAL] APEX episode start: task_id={record.task_id}, budget={budget_tokens}"
        )

        epoch_switches = 0

        try:
            # Prepare workspace with repository at base commit
            repo_path = RepoManager.prepare_workspace(
                record=record,
                work_root=str(self.work_root),
                oracle=self.oracle_smoke,
            )

            # If in oracle mode, just run tests (gold patch already applied)
            if self.oracle_smoke:
                self.logger.info("[EVAL] Oracle mode: running validation tests only")
                test_result = RepoManager.run_tests(
                    repo_path=repo_path,
                    test_select=record.fail_to_pass if record.fail_to_pass else None,
                    timeout_s=180,
                )
                success = test_result["exit_code"] == 0 and test_result["failed"] == 0
                tokens_used = int(test_result["duration_s"] * 100) + 1000
                self.logger.info(
                    f"[EVAL] Oracle result: success={success}, "
                    f"test_duration={test_result['duration_s']:.2f}s"
                )
                return success, tokens_used, 0

            # Create APEX stack for dynamic topology switching
            self.logger.info("[EVAL] Initializing APEX stack components")

            # 1. Create Router with epoch-gated queues
            router = Router(queue_cap_per_agent=1000, fanout_cap=2)

            # 2. Create SwitchEngine for atomic topology transitions
            switch_engine = SwitchEngine(router=router, quiesce_deadline_ms=50)

            # 3. Create Coordinator for dwell/cooldown enforcement
            coordinator = Coordinator(switch_engine=switch_engine)

            # 4. Create BanditSwitchV1 for topology decisions
            from apex.controllers.bandit_switch import BanditSwitchV1
            from apex.controllers.feature_source import FeatureSource
            
            bandit = BanditSwitchV1(
                epsilon_start=0.3, epsilon_end=0.1, epsilon_decay=0.995, learning_rate=0.01
            )

            # 5. Create FeatureSource for bandit context
            feature_source = FeatureSource()

            # 6. Create APEXController to orchestrate everything
            controller = APEXController(
                bandit=bandit,
                feature_src=feature_source,
                coordinator=coordinator,
                switch=switch_engine,
                budget=budget_tokens,
            )

            # 7. Create MessageSWEAgent with APEX integration
            episode_id = str(uuid.uuid4())
            agent_id = AgentID("message_swe_agent")

            # Create LLM and FS instances 
            llm = None  # Will use default LLM client from existing harness logic
            
            # Create MCP filesystem adapter sandboxed to repo path
            from apex.integrations.mcp.fs_local import LocalFS
            fs = LocalFS(root=str(repo_path))
            
            message_agent = MessageSWEAgent(
                agent_id=agent_id,
                router=router,
                switch=switch_engine,
                fs=fs,
                episode_id=episode_id,
                llm=llm,
            )

            self.logger.info("[EVAL] APEX stack initialized, starting MessageSWEAgent")

            # Run MessageSWEAgent with dynamic topology switching
            async def run_with_apex():
                nonlocal epoch_switches

                try:
                    # Start the APEX controller monitoring in the background
                    controller_task = None
                    try:
                        # Enhanced controller loop with phase awareness
                        async def controller_loop():
                            last_phase = "analysis"
                            phase_start_time = time.time()
                            
                            while True:
                                # Check current task phase
                                current_phase = None
                                if message_agent.active_tasks:
                                    task = next(iter(message_agent.active_tasks.values()))
                                    current_phase = task.phase
                                
                                # Phase transition detected - good time to consider switching
                                if current_phase and current_phase != last_phase:
                                    phase_duration = time.time() - phase_start_time
                                    self.logger.info(
                                        f"[APEX] Phase transition: {last_phase} -> {current_phase} "
                                        f"(duration: {phase_duration:.1f}s)"
                                    )
                                    
                                    # Update feature source with phase info
                                    controller.features.update_phase(current_phase)
                                    
                                    # Controller decides on topology
                                    decision = await controller.tick()
                                    coordinator.step()

                                    # Track topology switches
                                    if decision.get("switch", {}).get("committed", False):
                                        nonlocal epoch_switches
                                        epoch_switches += 1
                                        topo_after = decision.get("topology_after")
                                        self.logger.info(
                                            f"[EVAL] Topology switched to {topo_after} for "
                                            f"{current_phase} phase, switches: {epoch_switches}"
                                        )
                                        
                                        # Notify agents of topology change
                                        if hasattr(message_agent, '_notify_topology_change'):
                                            await message_agent._notify_topology_change(
                                                task.task_id, topo_after
                                            )
                                    
                                    last_phase = current_phase
                                    phase_start_time = time.time()

                                # Regular controller tick
                                await asyncio.sleep(1.0)  # Check less frequently

                        # Start controller in background
                        controller_task = asyncio.create_task(controller_loop())

                        # Run the actual SWE solving task
                        success, tokens_used = await message_agent.solve_task(
                            problem_statement=record.problem_statement,
                            repo_path=Path(repo_path),
                            fail_tests=record.fail_to_pass if record.fail_to_pass else [],
                            budget=budget_tokens,
                        )

                        return success, tokens_used

                    except Exception as e:
                        self.logger.error(f"[EVAL] Error in APEX controller/agent: {e}")
                        return False, budget_tokens
                    finally:
                        # Clean up controller task
                        if controller_task:
                            controller_task.cancel()
                            try:
                                await controller_task
                            except asyncio.CancelledError:
                                pass

                except Exception as e:
                    self.logger.error(f"[EVAL] Error in APEX episode: {e}")
                    return False, budget_tokens

            # Run the async APEX episode
            success, tokens_used = asyncio.run(run_with_apex())

            # If agent claims success, verify with actual test run
            if success:
                self.logger.info("[EVAL] MessageSWEAgent claims success, verifying with tests")
                verify_start = time.time()
                test_result = RepoManager.run_tests(
                    repo_path=repo_path,
                    test_select=record.fail_to_pass if record.fail_to_pass else None,
                    timeout_s=180,
                )
                verify_time = time.time() - verify_start
                success = test_result["exit_code"] == 0 and test_result["failed"] == 0
                self.logger.info(
                    f"[EVAL] Verification: passed={test_result.get('passed', 0)}, "
                    f"failed={test_result.get('failed', 0)}, exit_code={test_result['exit_code']}, "
                    f"time={verify_time:.2f}s, switches={epoch_switches}"
                )
                self.logger.info(f"[EVAL] Final APEX task success: {success}")

            return success, tokens_used, epoch_switches

        except Exception as e:
            # Log error and treat as failure
            apex_time = time.time() - apex_start
            self.logger.error(
                f"[EVAL] APEX episode error: task={record.task_id}, error={e}, "
                f"time={apex_time:.2f}s"
            )
            return False, budget_tokens, epoch_switches

    def cleanup(self):
        """Clean up workspace after evaluation."""
        if hasattr(self, "work_root") and self.work_root.exists():
            self.logger.info(f"[EVAL] Cleaning up workspace: {self.work_root}")
            RepoManager.cleanup_workspace(str(self.work_root))
            self.logger.info("[EVAL] Cleanup completed")
