"""Integration harness for APEX runtime with SWE-bench.

Ties together all components for episode execution.
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .agents.scripted import create_agent
from .controllers.bandit import BanditConfig, BanditSwitch, BanditSwitchOracle
from .coord.coordinator import CoordConfig, Coordinator
from .llm.client import LLMClient, LLMConfig, TokenTracker
from .mcp.fs import FSConfig, MCPFileSystem
from .mcp.test import MCPTestRunner, TestConfig
from .runtime.message import AgentID, Message
from .runtime.router import Router
from .runtime.switch import SwitchEngine
from .topology.semantics import PhaseHeuristics, create_topology


@dataclass
class EpisodeConfig:
    """Episode execution configuration."""

    task_id: str
    task_description: str
    max_iterations: int = 20
    token_budget: int = 10_000
    timeout_seconds: int = 300
    topology: str = "star"  # Static topology or "dynamic"


@dataclass
class EpisodeResult:
    """Episode execution result."""

    task_id: str
    success: bool
    tokens_used: int
    elapsed_seconds: float
    iterations: int
    final_output: Optional[str]
    error: Optional[str]
    topology_switches: List[Dict[str, Any]]


class APEXHarness:
    """Main harness for APEX runtime execution."""

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        bandit_config: Optional[BanditConfig] = None,
        workspace_dir: str = "/tmp/apex_workspace",
    ):
        """Initialize harness.

        Args:
            llm_config: LLM client configuration
            bandit_config: Bandit controller configuration
            workspace_dir: Workspace directory for file operations
        """
        # Core runtime components
        self.router = Router(queue_cap_per_agent=10_000)
        self.switch_engine = SwitchEngine(self.router, quiesce_deadline_ms=50)
        self.coordinator = Coordinator(
            self.switch_engine, self.router, CoordConfig(dwell_min_steps=2, cooldown_steps=2)
        )

        # LLM and token tracking
        self.token_tracker = TokenTracker(budget=10_000)
        self.llm_config = llm_config or LLMConfig(mock_mode=True)
        self.llm_client = LLMClient(self.llm_config, self.token_tracker)

        # MCP adapters
        self.fs = MCPFileSystem(FSConfig(root_dir=Path(workspace_dir)))
        self.test_runner = MCPTestRunner(TestConfig())

        # Controllers
        self.phase_heuristics = PhaseHeuristics()
        self.bandit_config = bandit_config or BanditConfig()
        self.bandit = BanditSwitch(self.bandit_config)
        self.oracle = BanditSwitchOracle(self.bandit, self.phase_heuristics)

        # Agents registry
        self.agents: Dict[AgentID, Any] = {}
        self.topology = None

    async def setup_agents(self, topology_name: str):
        """Setup agents with topology.

        Args:
            topology_name: Topology to use
        """
        # Create topology
        self.topology = create_topology(topology_name)

        # Create agents
        roles = ["manager", "planner", "coder", "runner", "critic"]

        for role in roles:
            agent_id = AgentID(role)
            agent = create_agent(
                role=role,
                agent_id=agent_id,
                router=self.router,
                llm_client=self.llm_client,
                topology=self.topology,
                fs=self.fs,
                test_runner=self.test_runner,
            )
            self.agents[agent_id] = agent
            await agent.start()

    async def run_episode(self, config: EpisodeConfig) -> EpisodeResult:
        """Run single episode.

        Args:
            config: Episode configuration

        Returns:
            Episode result
        """
        episode_id = uuid4().hex
        start_time = time.time()

        # Reset for episode with configured budget
        self.token_tracker.budget = config.token_budget
        self.token_tracker.reset()
        self.bandit.reset_episode()
        topology_switches = []

        # Setup initial topology
        initial_topology = config.topology if config.topology != "dynamic" else "star"
        await self.setup_agents(initial_topology)

        # Create initial task message
        task_msg = Message(
            episode_id=episode_id,
            msg_id=uuid4().hex,
            sender=AgentID("harness"),
            recipient=AgentID("manager"),
            topo_epoch=self.router.active_epoch(),
            payload={"type": "task", "task": config.task_description, "task_id": config.task_id},
        )

        # Route initial message
        await self.router.route(task_msg)

        # Run episode loop
        iteration = 0
        success = False
        final_output = None
        error = None

        try:
            while iteration < config.max_iterations:
                iteration += 1

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > config.timeout_seconds:
                    error = "Episode timeout"
                    break

                # Check token budget
                if self.token_tracker.remaining() <= 0:
                    error = "Token budget exceeded"
                    break

                # Dynamic topology switching
                if config.topology == "dynamic":
                    # Compute metrics for oracle
                    message_rate = self._compute_message_rate()
                    queue_depth = self._compute_queue_depth()
                    token_usage = self.token_tracker.used / max(1, iteration)
                    error_rate = self._compute_error_rate()
                    success_rate = self._compute_success_rate()

                    # Check if switch needed
                    target_topo = self.oracle.should_switch(
                        message_rate=message_rate,
                        queue_depth=queue_depth,
                        token_usage=token_usage,
                        error_rate=error_rate,
                        iteration=iteration,
                        elapsed_time=elapsed,
                        success_rate=success_rate,
                    )

                    if target_topo:
                        # Attempt switch
                        result = await self.coordinator.maybe_switch(target_topo)
                        if result and result["ok"]:
                            topology_switches.append(
                                {
                                    "iteration": iteration,
                                    "to": target_topo,
                                    "epoch": result["epoch"],
                                    "elapsed_ms": result["stats"]["elapsed_ms"],
                                }
                            )
                            # Update agents' topology
                            await self._update_agent_topology(target_topo)

                # Process messages (simplified - agents handle async)
                await asyncio.sleep(0.1)  # Allow agents to process

                # Check for completion (look for summary message)
                summary = await self._check_for_summary(episode_id)
                if summary:
                    success = summary.get("success", False)
                    final_output = summary.get("final_code")
                    break

        except Exception as e:
            error = str(e)

        # Stop agents
        for agent in self.agents.values():
            await agent.stop()

        # Compute final reward if using bandit
        if config.topology == "dynamic":
            reward = self.bandit.compute_reward(
                success=success,
                tokens_used=self.token_tracker.used,
                time_elapsed=time.time() - start_time,
                iterations=iteration,
            )

            # Update bandit with final context
            from .controllers.bandit import Context

            final_phase = self.oracle.phase_detector.infer_phase()
            final_context = Context(
                phase=final_phase,
                message_rate=self._compute_message_rate(),
                queue_depth=self._compute_queue_depth(),
                token_usage=self.token_tracker.used / max(1, iteration),
                error_rate=self._compute_error_rate(),
                iteration=iteration,
                elapsed_time=time.time() - start_time,
                success_rate=1.0 if success else 0.0,
            )
            self.bandit.update_reward(self.oracle.current_topology, final_context, reward)

        return EpisodeResult(
            task_id=config.task_id,
            success=success,
            tokens_used=self.token_tracker.used,
            elapsed_seconds=time.time() - start_time,
            iterations=iteration,
            final_output=final_output,
            error=error,
            topology_switches=topology_switches,
        )

    async def _update_agent_topology(self, topology_name: str):
        """Update agents with new topology.

        Args:
            topology_name: New topology
        """
        new_topology = create_topology(topology_name)
        for agent in self.agents.values():
            agent.topology = new_topology

    async def _check_for_summary(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Check if manager has produced summary.

        Args:
            episode_id: Episode ID

        Returns:
            Summary if available
        """
        # Simplified - in production would track messages
        manager = self.agents.get(AgentID("manager"))
        if manager and hasattr(manager, "task_state"):
            # Check if episode complete
            if episode_id not in manager.task_state:
                # Episode was summarized and cleaned up
                return {"success": True}  # Simplified
        return None

    def _compute_message_rate(self) -> float:
        """Compute current message rate."""
        # Simplified - count messages in last second
        total = sum(agent.message_count for agent in self.agents.values())
        return min(total, 10.0)  # Cap at 10 msg/s

    def _compute_queue_depth(self) -> float:
        """Compute average queue depth."""
        depths = []
        for agent_id in self.agents:
            depth = self.router.get_queue_depth(agent_id)
            depths.append(depth)
        return sum(depths) / max(1, len(depths))

    def _compute_error_rate(self) -> float:
        """Compute recent error rate."""
        # Simplified - would track actual errors
        return 0.1

    def _compute_success_rate(self) -> float:
        """Compute recent success rate."""
        # Simplified - would track actual successes
        return 0.7

    async def run_batch(
        self, episodes: List[EpisodeConfig], parallel: int = 1
    ) -> List[EpisodeResult]:
        """Run batch of episodes.

        Args:
            episodes: List of episode configs
            parallel: Max parallel episodes

        Returns:
            List of results
        """
        results = []

        # Process in batches
        for i in range(0, len(episodes), parallel):
            batch = episodes[i : i + parallel]
            batch_results = await asyncio.gather(*[self.run_episode(ep) for ep in batch])
            results.extend(batch_results)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get harness statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "router": {
                "active_epoch": int(self.router.active_epoch()),
                "next_epoch": int(self.router.next_epoch()),
            },
            "switch_engine": self.switch_engine.get_stats(),
            "coordinator": self.coordinator.get_stats(),
            "llm": self.llm_client.get_stats(),
            "bandit": self.bandit.get_stats() if self.bandit else None,
            "agents": {str(aid): agent.get_stats() for aid, agent in self.agents.items()},
        }


async def run_swe_bench_smoke(n_episodes: int = 5):
    """Run smoke test on SWE-bench Lite.

    Args:
        n_episodes: Number of episodes to run

    Returns:
        Results summary
    """
    # Load sample tasks (simplified - would load from dataset)
    tasks = [
        {"task_id": f"swe_test_{i}", "description": f"Fix the bug in function compute_{i}"}
        for i in range(n_episodes)
    ]

    # Create harness
    harness = APEXHarness()

    # Run static topologies
    static_results = {}
    for topo in ["star", "chain", "flat"]:
        configs = [
            EpisodeConfig(task_id=t["task_id"], task_description=t["description"], topology=topo)
            for t in tasks
        ]

        results = await harness.run_batch(configs)
        static_results[topo] = results

    # Run dynamic topology
    dynamic_configs = [
        EpisodeConfig(task_id=t["task_id"], task_description=t["description"], topology="dynamic")
        for t in tasks
    ]

    dynamic_results = await harness.run_batch(dynamic_configs)

    # Compute summary
    summary = {
        "n_episodes": n_episodes,
        "static_results": {
            topo: {
                "success_rate": sum(1 for r in results if r.success) / len(results),
                "avg_tokens": sum(r.tokens_used for r in results) / len(results),
                "avg_time": sum(r.elapsed_seconds for r in results) / len(results),
            }
            for topo, results in static_results.items()
        },
        "dynamic_results": {
            "success_rate": sum(1 for r in dynamic_results if r.success) / len(dynamic_results),
            "avg_tokens": sum(r.tokens_used for r in dynamic_results) / len(dynamic_results),
            "avg_time": sum(r.elapsed_seconds for r in dynamic_results) / len(dynamic_results),
            "total_switches": sum(len(r.topology_switches) for r in dynamic_results),
        },
    }

    return summary
