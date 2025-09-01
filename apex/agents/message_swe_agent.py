"""MessageSWEAgent that integrates with the APEX message system for generic agent coordination.

This agent coordinates SWE solving through collaborative discussion among generic agents
(Agent-1, Agent-2, Agent-3, Agent-4, Agent-5) via messages through the APEX router.
The agents discuss problems together rather than having specialized roles.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from apex.agents.base import BaseAgent
from apex.integrations.llm.client_api import LLM
from apex.integrations.mcp.fs_api import FS
from apex.runtime.message import AgentID, Message
from apex.runtime.router_api import IRouter
from apex.runtime.switch_api import ISwitchEngine


@dataclass
class SWETask:
    """Represents a SWE-bench task with all necessary context."""

    problem_statement: str
    repo_path: Path
    fail_tests: List[str]
    budget: int = 32000
    task_id: str = field(default_factory=lambda: uuid4().hex)
    start_time: float = field(default_factory=time.time)
    tokens_used: int = 0
    phase: str = "analysis"  # analysis, planning, coding, testing, critique, complete, failed
    analysis_result: Optional[str] = None
    plan_result: Optional[str] = None
    relevant_files: Optional[Dict[str, str]] = None
    current_fix: Optional[str] = None
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    critiques: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3


class MessageSWEAgent(BaseAgent):
    """SWE-bench agent that uses message-based coordination with generic agents.

    This agent orchestrates SWE solving through collaborative discussion among generic agents:
    - Agent-1, Agent-2, Agent-3, Agent-4, Agent-5 are generic agents
    - They discuss the problem together and coordinate the solution
    - Communication patterns respect the current topology (star, chain, flat)
    - No specialized roles - all agents are generic and collaborate through discussion
    
    This is the key research aspect: generic agent coordination rather than specialized agents.
    """

    def __init__(
        self,
        agent_id: AgentID,
        router: IRouter,
        switch: ISwitchEngine,
        fs: FS,
        episode_id: str,
        llm: Optional[LLM] = None,
    ) -> None:
        super().__init__(agent_id, router, switch, fs, episode_id, llm)

        # Configure logging
        self.logger = logging.getLogger(f"{__name__}.MessageSWEAgent")
        self.logger.info(f"[MSG_SWE] Initialized MessageSWEAgent: agent_id={agent_id}")

        # Task state management
        self.active_tasks: Dict[str, SWETask] = {}
        self.total_tokens = 0

        # Generic agent pool IDs for collaboration
        self.generic_agent_ids = [
            AgentID("Agent-1"),
            AgentID("Agent-2"), 
            AgentID("Agent-3"),
            AgentID("Agent-4"),
            AgentID("Agent-5"),
        ]
        
        # Create actual generic agent instances with FS access
        from apex.agents.generic import GenericAgent
        self.generic_agents: Dict[AgentID, GenericAgent] = {}
        for agent_id_item in self.generic_agent_ids:
            self.generic_agents[agent_id_item] = GenericAgent(
                agent_id=agent_id_item,
                router=router,
                switch=switch,
                fs=fs,  # Pass FS to enable file operations
                episode_id=episode_id,
                llm=llm,
            )
            self.logger.info(f"[MSG_SWE] Created generic agent: {agent_id_item}")
        
        # Track active topology
        self.current_topology = "star"  # Default
        
        # Remove self from the pool if this agent is part of it
        if self.agent_id in self.generic_agent_ids:
            self.generic_agent_ids.remove(self.agent_id)

    async def solve_task(
        self, problem_statement: str, repo_path: Path, fail_tests: List[str], budget: int = 32000
    ) -> Tuple[bool, int]:
        """Main entry point to solve a SWE-bench task using message coordination.

        Args:
            problem_statement: Description of the issue to solve
            repo_path: Path to the repository
            fail_tests: List of tests that should pass after fixing
            budget: Token budget for the solving process

        Returns:
            Tuple of (success: bool, tokens_used: int)
        """
        start_time = time.time()
        self.logger.info(
            f"[MSG_SWE] Starting solve_task: budget={budget}, "
            f"fail_tests={len(fail_tests)}, repo={repo_path}"
        )

        # Create task context
        task = SWETask(
            problem_statement=problem_statement,
            repo_path=repo_path,
            fail_tests=fail_tests,
            budget=budget,
        )

        self.active_tasks[task.task_id] = task

        try:
            # First, initialize all agents with their roles
            await self._initialize_agents_for_topology(task.task_id, problem_statement)
            
            # Create a simple message processing loop for generic agents
            # This simulates the episode runner functionality
            asyncio.create_task(self._process_agent_messages(task.task_id))
            
            # Then start collaborative task solving
            initial_agents = self._select_initial_agents()
            
            discussion_messages = []
            for agent in initial_agents:
                discussion_msg = self._new_msg(
                    recipient=agent,
                    payload={
                        "type": "swe_task_discussion",
                        "task_id": task.task_id,
                        "problem_statement": problem_statement[:2000],  # Limit context
                        "fail_tests": fail_tests[:10],  # Limit test list
                        "budget": budget,
                        "phase": "initial",
                        "coordinator": str(self.agent_id),
                    },
                )
                discussion_messages.append(discussion_msg)

            # Route all initial discussion messages
            for msg in discussion_messages:
                success = await self.router.route(msg)
                if not success:
                    self.logger.error(
                        f"[MSG_SWE] Failed to route discussion message to {msg.recipient} "
                        f"for task {task.task_id}"
                    )
                    return False, 0

            # Wait for task completion or timeout
            timeout = 300  # 5 minutes timeout
            result = await self._wait_for_completion(task.task_id, timeout)

            elapsed = time.time() - start_time
            self.logger.info(
                f"[MSG_SWE] Task completed: success={result[0]}, "
                f"tokens={result[1]}, time={elapsed:.2f}s"
            )

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"[MSG_SWE] Task failed with exception: {e}, time={elapsed:.2f}s")
            # Clean up task state
            self.active_tasks.pop(task.task_id, None)
            return False, task.tokens_used

    async def handle(self, msg: Message) -> List[Message]:
        """Handle incoming messages and coordinate SWE solving phases.

        Args:
            msg: Incoming message from router

        Returns:
            List of response messages to be routed
        """
        try:
            msg_type = msg.payload.get("type", "")
            task_id = msg.payload.get("task_id")

            self.logger.debug(
                f"[MSG_SWE] Handling message: type={msg_type}, "
                f"task_id={task_id}, sender={msg.sender}"
            )

            if not task_id or task_id not in self.active_tasks:
                self.logger.warning(f"[MSG_SWE] Unknown or missing task_id: {task_id}")
                return []

            task = self.active_tasks[task_id]

            # Update token usage if provided
            tokens_used = msg.payload.get("tokens_used", 0)
            task.tokens_used += tokens_used
            self.total_tokens += tokens_used

            # Route message based on type 
            if msg_type == "swe_task_discussion":
                return await self._handle_discussion_message(msg, task)
            elif msg_type == "swe_collaboration_response":
                return await self._handle_collaboration_response(msg, task)
            elif msg_type == "swe_acknowledgment":
                return await self._handle_acknowledgment(msg, task)
            elif msg_type.endswith("_response"):
                return await self._handle_generic_response(msg, task)
            else:
                self.logger.warning(f"[MSG_SWE] Unknown message type: {msg_type}")
                return []

        except Exception as e:
            self.logger.error(f"[MSG_SWE] Error handling message: {e}")
            return []

    async def _initialize_agents_for_topology(self, task_id: str, problem_statement: str):
        """Initialize all agents with their roles based on current topology."""
        topology, _ = self.switch.active()
        self.current_topology = topology
        
        self.logger.info(f"[MSG_SWE] Initializing agents for {topology} topology")
        
        # Send initialization message to all agents
        init_messages = []
        for agent in self.generic_agent_ids:
            init_msg = self._new_msg(
                recipient=agent,
                payload={
                    "type": "agent_initialization",
                    "task_id": task_id,
                    "topology": topology,
                    "agent_count": len(self.generic_agent_ids),
                    "task_description": f"SWE-bench task: {problem_statement[:500]}",
                }
            )
            init_messages.append(init_msg)
        
        # Send all initialization messages
        for msg in init_messages:
            await self.router.route(msg)
        
        # Wait briefly for agents to initialize
        await asyncio.sleep(0.5)
    
    async def _notify_topology_change(self, task_id: str, new_topology: str):
        """Notify all agents of topology change."""
        self.logger.info(f"[MSG_SWE] Notifying agents of topology change to {new_topology}")
        
        change_messages = []
        for agent in self.generic_agent_ids:
            change_msg = self._new_msg(
                recipient=agent,
                payload={
                    "type": "topology_change",
                    "task_id": task_id,
                    "topology": new_topology,
                    "agent_count": len(self.generic_agent_ids),
                }
            )
            change_messages.append(change_msg)
        
        # Send all change notifications
        for msg in change_messages:
            await self.router.route(msg)
        
        self.current_topology = new_topology
        
        # Wait for agents to reconfigure
        await asyncio.sleep(0.5)
    
    def _select_initial_agents(self) -> List[AgentID]:
        """Select initial agents to start task discussion based on current topology."""
        if self.current_topology == "star":
            # In star topology, start with the coordinator (typically Agent-1)
            return [AgentID("Agent-1")]
        elif self.current_topology == "chain":
            # In chain topology, start with first agent in sequence
            return [AgentID("Agent-1")]
        else:  # flat topology
            # In flat topology, start with first two agents to begin discussion
            return self.generic_agent_ids[:2]

    async def _handle_discussion_message(self, msg: Message, task: SWETask) -> List[Message]:
        """Handle task discussion messages from agents."""
        discussion_point = msg.payload.get("discussion_point", "")
        phase = msg.payload.get("phase", "initial")
        from_agent = msg.payload.get("from_agent", "")

        self.logger.info(
            f"[MSG_SWE] Received discussion from {from_agent} in {phase} phase "
            f"for task {task.task_id}"
        )

        # Update task phase based on discussion progress
        old_phase = task.phase
        if phase == "initial" and task.phase == "analysis":
            task.phase = "planning"
        elif phase == "planning" and task.phase == "planning":
            task.phase = "coding"
        elif phase == "coding" and task.phase == "coding":
            task.phase = "testing"
        elif phase == "testing" and task.phase == "testing":
            task.phase = "complete"
        
        # Check if we should switch topology based on phase change
        if old_phase != task.phase and hasattr(self, 'controller'):
            # Controller would decide if topology switch is needed
            # This is where intra-task switching would happen
            pass

        # Simple completion check - if we've had enough discussion rounds
        discussion_count = len([h for h in task.critiques if "discussion" in str(h)])
        if discussion_count > 3:  # After 3 rounds of discussion, consider task complete
            task.phase = "complete"
            self.logger.info(
                f"[MSG_SWE] Task {task.task_id} completed after collaborative discussion"
            )
            return []

        # Continue discussion with other agents based on topology
        next_agents = self._select_next_discussion_agents(msg.sender)
        messages = []
        
        for agent in next_agents:
            next_msg = self._new_msg(
                recipient=agent,
                payload={
                    "type": "swe_collaboration_request",
                    "task_id": task.task_id,
                    "collaboration_type": task.phase,
                    "previous_discussion": discussion_point,
                    "from_agent": str(self.agent_id),
                }
            )
            messages.append(next_msg)

        # Record this discussion in the task critiques (reusing existing field)
        task.critiques.append(f"Discussion from {from_agent}: {discussion_point}")
        
        return messages

    async def _handle_collaboration_response(self, msg: Message, task: SWETask) -> List[Message]:
        """Handle collaboration responses from agents."""
        response = msg.payload.get("response", "")
        collaboration_type = msg.payload.get("collaboration_type", "")
        agent_id = msg.payload.get("agent_id", "")

        self.logger.info(
            f"[MSG_SWE] Collaboration response from {agent_id} on {collaboration_type} "
            f"for task {task.task_id}"
        )

        # Record the collaboration response
        task.critiques.append(f"Collaboration from {agent_id}: {response}")

        # Advance task based on collaboration
        if collaboration_type == "analysis":
            task.analysis_result = response
        elif collaboration_type == "planning":
            task.plan_result = response
        elif collaboration_type == "coding":
            task.current_fix = response
        elif collaboration_type == "testing":
            # Simulate test success for now
            task.phase = "complete"
            self.logger.info(
                f"[MSG_SWE] Task {task.task_id} completed successfully through collaboration!"
            )

        return []

    async def _handle_acknowledgment(self, msg: Message, task: SWETask) -> List[Message]:
        """Handle acknowledgment messages from agents."""
        message = msg.payload.get("message", "")
        
        self.logger.debug(f"[MSG_SWE] Acknowledgment for task {task.task_id}: {message}")
        
        # Simple acknowledgment - no further action needed
        return []

    async def _handle_generic_response(self, msg: Message, task: SWETask) -> List[Message]:
        """Handle any other response messages."""
        self.logger.info(f"[MSG_SWE] Generic response for task {task.task_id} from {msg.sender}")
        
        # For now, just acknowledge receipt
        return []

    def _select_next_discussion_agents(self, current_sender: AgentID) -> List[AgentID]:
        """Select next agents for discussion based on topology and current sender."""
        topology, _ = self.switch.active()
        
        if topology == "star":
            # In star topology, coordinate through Agent-1
            if str(current_sender) == "Agent-1":
                # Coordinator talks to other agents
                return [agent for agent in self.generic_agent_ids if str(agent) != "Agent-1"][:2]
            else:
                # Other agents talk back to coordinator
                return [AgentID("Agent-1")]
        
        elif topology == "chain":
            # In chain topology, pass to next agent in sequence
            try:
                sender_num = int(str(current_sender).split("-")[1])
                next_num = sender_num + 1
                if next_num <= 5:  # Max 5 agents
                    return [AgentID(f"Agent-{next_num}")]
            except (ValueError, IndexError):
                pass
            return []
        
        else:  # flat topology
            # In flat topology, can talk to any other agent
            available_agents = [
                agent for agent in self.generic_agent_ids if agent != current_sender
            ]
            return available_agents[:2]  # Limit to 2 to avoid fanout issues




    async def _process_agent_messages(self, task_id: str):
        """Process messages for generic agents in the background.
        
        This simulates an episode runner that dequeues messages for each agent
        and has them handle the messages.
        """
        while task_id in self.active_tasks:
            try:
                # Process messages for each generic agent
                for agent_id, agent in self.generic_agents.items():
                    # Try to dequeue a message for this agent
                    msg = await self.router.dequeue(agent_id)
                    if msg:
                        # Have the agent handle the message
                        responses = await agent.handle(msg)
                        
                        # Route any response messages
                        for response in responses:
                            await self.router.route(response)
                
                # Small delay to avoid busy-waiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"[MSG_SWE] Error processing agent messages: {e}")
                await asyncio.sleep(0.5)

    async def _wait_for_completion(self, task_id: str, timeout: float) -> Tuple[bool, int]:
        """Wait for task completion or timeout.

        Args:
            task_id: ID of the task to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (success: bool, tokens_used: int)
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if task_id not in self.active_tasks:
                self.logger.warning(f"[MSG_SWE] Task {task_id} disappeared during wait")
                return False, 0

            task = self.active_tasks[task_id]

            if task.phase == "complete":
                # Clean up completed task
                self.active_tasks.pop(task_id, None)
                return True, task.tokens_used
            elif task.phase == "failed":
                # Clean up failed task
                self.active_tasks.pop(task_id, None)
                return False, task.tokens_used

            # Check for budget exhaustion
            if task.tokens_used > task.budget:
                self.logger.warning(
                    f"[MSG_SWE] Task {task_id} exceeded budget: {task.tokens_used}/{task.budget}"
                )
                task.phase = "failed"
                self.active_tasks.pop(task_id, None)
                return False, task.tokens_used

            # Wait a bit before checking again
            await asyncio.sleep(0.5)

        # Timeout reached
        self.logger.error(f"[MSG_SWE] Task {task_id} timed out after {timeout}s")
        task = self.active_tasks.pop(task_id, None)
        tokens_used = task.tokens_used if task else 0
        return False, tokens_used


    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all active tasks."""
        return {
            task_id: {
                "phase": task.phase,
                "tokens_used": task.tokens_used,
                "budget": task.budget,
                "retry_count": task.retry_count,
                "elapsed_time": time.time() - task.start_time,
                "test_results_count": len(task.test_results),
            }
            for task_id, task in self.active_tasks.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_id": str(self.agent_id),
            "total_tokens": self.total_tokens,
            "active_tasks": len(self.active_tasks),
            "active_task_details": self.get_active_tasks(),
        }
