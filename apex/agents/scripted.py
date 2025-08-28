"""Scripted agents with topology-aware behavior.

Implements planner, coder, runner, critic, and summarizer agents.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from ..llm.client import LLMClient
from ..mcp.fs import FSConfig, MCPFileSystem
from ..mcp.test import MCPTestRunner, TestConfig
from ..runtime.message import AgentID, Message
from ..runtime.router import Router
from ..topology.semantics import TopologySemantics


@dataclass
class AgentConfig:
    """Agent configuration."""

    agent_id: AgentID
    role: str
    system_prompt: str
    max_retries: int = 3
    response_timeout: float = 30.0


class ScriptedAgent:
    """Base class for scripted agents.

    Handles message processing with topology awareness.
    """

    def __init__(
        self,
        config: AgentConfig,
        router: Router,
        llm_client: LLMClient,
        topology: Optional[TopologySemantics] = None,
    ):
        """Initialize agent.

        Args:
            config: Agent configuration
            router: Message router
            llm_client: LLM client
            topology: Current topology semantics
        """
        self.config = config
        self.router = router
        self.llm = llm_client
        self.topology = topology
        self.running = False
        self.message_count = 0

    async def start(self):
        """Start agent processing loop."""
        self.running = True
        asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop agent processing."""
        self.running = False

    async def _process_loop(self):
        """Main message processing loop."""
        while self.running:
            try:
                # Dequeue message
                msg = await self.router.dequeue(self.config.agent_id, timeout=1.0)

                if msg:
                    self.message_count += 1
                    await self._handle_message(msg)

            except Exception as e:
                # Log error (simplified for MVP)
                print(f"Agent {self.config.agent_id} error: {e}")

    async def _handle_message(self, msg: Message):
        """Handle incoming message.

        Args:
            msg: Message to handle
        """
        # Process based on role
        response = await self._process(msg)

        if response:
            # Send response respecting topology
            await self._send_response(response, msg)

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Process message based on agent role.

        Args:
            msg: Message to process

        Returns:
            Response payload or None
        """
        # Subclasses implement specific processing
        raise NotImplementedError

    async def _send_response(self, payload: Dict[str, Any], original_msg: Message):
        """Send response message respecting topology.

        Args:
            payload: Response payload
            original_msg: Original message being responded to
        """
        # Determine valid recipients based on topology
        if self.topology:
            # Get all agents (simplified - would track in production)
            all_agents = {
                AgentID("manager"),
                AgentID("planner"),
                AgentID("coder"),
                AgentID("runner"),
                AgentID("critic"),
            }
            valid_recipients = self.topology.get_next_recipients(self.config.agent_id, all_agents)
        else:
            # No topology, send back to sender
            valid_recipients = {original_msg.sender}

        # Check if this would be a broadcast in flat topology
        if len(valid_recipients) > 1:
            # In flat topology, stamp fanout for router validation
            payload = payload.copy()  # Don't mutate original
            payload["_fanout"] = len(valid_recipients)

            # For MVP, send to up to 2 recipients (flat topology limit)
            valid_recipients = set(list(valid_recipients)[:2])

        # Send to first valid recipient (simplified routing)
        if valid_recipients:
            recipient = next(iter(valid_recipients))

            response_msg = Message(
                episode_id=original_msg.episode_id,
                msg_id=uuid4().hex,
                sender=self.config.agent_id,
                recipient=recipient,
                topo_epoch=original_msg.topo_epoch,  # Use same epoch
                payload=payload,
            )

            await self.router.route(response_msg)

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "agent_id": str(self.config.agent_id),
            "role": self.config.role,
            "messages_processed": self.message_count,
            "running": self.running,
        }


class PlannerAgent(ScriptedAgent):
    """Planner agent for task decomposition."""

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Create plan from task description."""
        task = msg.payload.get("task", "")

        # Use LLM to create plan
        prompt = f"""Given this task: {task}

Create a step-by-step plan with:
1. Clear objectives
2. Implementation steps
3. Test criteria
4. Success metrics

Be specific and actionable."""

        response = await self.llm.complete(prompt, self.config.system_prompt)

        if response.error:
            return {"error": response.error}

        return {
            "type": "plan",
            "plan": response.content,
            "task": task,
            "tokens_used": response.tokens_used,
        }


class CoderAgent(ScriptedAgent):
    """Coder agent for implementation."""

    def __init__(self, *args, fs: MCPFileSystem, **kwargs):
        """Initialize with file system access.

        Args:
            fs: File system adapter
        """
        super().__init__(*args, **kwargs)
        self.fs = fs

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Implement code based on plan."""
        plan = msg.payload.get("plan", "")
        task = msg.payload.get("task", "")

        # Use LLM to generate code
        prompt = f"""Task: {task}

Plan: {plan}

Generate Python code that implements this plan.
Include proper error handling and documentation."""

        response = await self.llm.complete(prompt, self.config.system_prompt)

        if response.error:
            return {"error": response.error}

        # Extract code from response
        code = self._extract_code(response.content)

        # Save to file system
        if code:
            try:
                await self.fs.write("solution.py", code)
                saved = True
            except Exception as e:
                saved = False
                code = f"# Failed to save: {e}\n{code}"
        else:
            saved = False

        return {"type": "code", "code": code, "saved": saved, "tokens_used": response.tokens_used}

    def _extract_code(self, content: str) -> str:
        """Extract code from LLM response."""
        if "```python" in content:
            start = content.index("```python") + 9
            end = content.index("```", start)
            return content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            return content[start:end].strip()
        return content


class RunnerAgent(ScriptedAgent):
    """Runner agent for test execution."""

    def __init__(self, *args, test_runner: MCPTestRunner, **kwargs):
        """Initialize with test runner.

        Args:
            test_runner: Test execution adapter
        """
        super().__init__(*args, **kwargs)
        self.runner = test_runner

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Execute code and tests."""
        code = msg.payload.get("code", "")

        if not code:
            return {"error": "No code to run"}

        # Check syntax first
        syntax_check = await self.runner.check_syntax(code)

        if not syntax_check["valid"]:
            return {
                "type": "test_result",
                "success": False,
                "error": syntax_check["error"],
                "stage": "syntax_check",
            }

        # Run code
        result = await self.runner.run_python(code)

        return {
            "type": "test_result",
            "success": result["success"],
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", -1),
            "elapsed": result.get("elapsed_seconds", 0),
        }


class CriticAgent(ScriptedAgent):
    """Critic agent for evaluation and feedback."""

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Evaluate results and provide feedback."""
        msg_type = msg.payload.get("type", "")

        if msg_type == "test_result":
            # Evaluate test results
            success = msg.payload.get("success", False)
            stdout = msg.payload.get("stdout", "")
            stderr = msg.payload.get("stderr", "")

            if success:
                feedback = "Tests passed successfully."
                needs_revision = False
            else:
                # Use LLM to analyze failure
                prompt = f"""Test execution failed.

Error output:
{stderr}

Standard output:
{stdout}

Analyze the failure and suggest fixes."""

                response = await self.llm.complete(prompt, self.config.system_prompt)
                feedback = response.content if not response.error else "Analysis failed"
                needs_revision = True

        else:
            # General evaluation
            prompt = f"""Evaluate this work product:

{json.dumps(msg.payload, indent=2)}

Provide constructive feedback on:
1. Correctness
2. Completeness  
3. Quality
4. Improvements needed"""

            response = await self.llm.complete(prompt, self.config.system_prompt)
            feedback = response.content if not response.error else "Evaluation failed"
            needs_revision = "improve" in feedback.lower() or "fix" in feedback.lower()

        return {
            "type": "critique",
            "feedback": feedback,
            "needs_revision": needs_revision,
            "original_type": msg_type,
        }


class ManagerAgent(ScriptedAgent):
    """Manager agent for orchestration and summarization."""

    def __init__(self, *args, **kwargs):
        """Initialize manager."""
        super().__init__(*args, **kwargs)
        self.task_state = {}

    async def _process(self, msg: Message) -> Optional[Dict[str, Any]]:
        """Orchestrate task execution."""
        msg_type = msg.payload.get("type", "")
        episode_id = msg.episode_id

        # Track task state
        if episode_id not in self.task_state:
            self.task_state[episode_id] = {
                "task": msg.payload.get("task", ""),
                "plan": None,
                "code": None,
                "test_results": [],
                "critiques": [],
                "iterations": 0,
            }

        state = self.task_state[episode_id]

        # Update state based on message type
        if msg_type == "plan":
            state["plan"] = msg.payload.get("plan")
        elif msg_type == "code":
            state["code"] = msg.payload.get("code")
        elif msg_type == "test_result":
            state["test_results"].append(msg.payload)
        elif msg_type == "critique":
            state["critiques"].append(msg.payload)

        state["iterations"] += 1

        # Decide next action
        if state["iterations"] >= 10:
            # Max iterations reached, summarize
            return await self._summarize(episode_id)
        elif not state["plan"]:
            # Need plan
            return {"type": "request", "request": "plan", "task": state["task"]}
        elif not state["code"]:
            # Need implementation
            return {
                "type": "request",
                "request": "implement",
                "plan": state["plan"],
                "task": state["task"],
            }
        elif len(state["test_results"]) == 0:
            # Need test run
            return {"type": "request", "request": "test", "code": state["code"]}
        elif msg_type == "critique" and msg.payload.get("needs_revision"):
            # Need revision
            return {
                "type": "request",
                "request": "revise",
                "code": state["code"],
                "feedback": msg.payload.get("feedback"),
            }
        else:
            # Task complete, summarize
            return await self._summarize(episode_id)

    async def _summarize(self, episode_id: str) -> Dict[str, Any]:
        """Create task summary."""
        state = self.task_state.get(episode_id, {})

        # Check if tests passed
        success = any(r.get("success") for r in state.get("test_results", []))

        summary = {
            "type": "summary",
            "episode_id": episode_id,
            "task": state.get("task"),
            "success": success,
            "iterations": state.get("iterations", 0),
            "final_code": state.get("code"),
            "test_results": (
                state.get("test_results", [])[-1] if state.get("test_results") else None
            ),
            "feedback": state.get("critiques", [])[-1] if state.get("critiques") else None,
        }

        # Clean up state
        del self.task_state[episode_id]

        return summary


def create_agent(
    role: str,
    agent_id: AgentID,
    router: Router,
    llm_client: LLMClient,
    topology: Optional[TopologySemantics] = None,
    **kwargs,
) -> ScriptedAgent:
    """Factory for creating agents.

    Args:
        role: Agent role
        agent_id: Agent ID
        router: Message router
        llm_client: LLM client
        topology: Topology semantics
        **kwargs: Role-specific arguments

    Returns:
        Agent instance
    """
    system_prompts = {
        "planner": "You are a planning agent. Create clear, actionable plans.",
        "coder": "You are a coding agent. Write clean, working Python code.",
        "runner": "You are a test runner agent. Execute and validate code.",
        "critic": "You are a critic agent. Provide constructive feedback.",
        "manager": "You are a manager agent. Orchestrate task execution.",
    }

    config = AgentConfig(
        agent_id=agent_id,
        role=role,
        system_prompt=system_prompts.get(role, "You are a helpful agent."),
    )

    if role == "planner":
        return PlannerAgent(config, router, llm_client, topology)
    elif role == "coder":
        fs = kwargs.get("fs") or MCPFileSystem(FSConfig(root_dir="/tmp/apex"))
        return CoderAgent(config, router, llm_client, topology, fs=fs)
    elif role == "runner":
        runner = kwargs.get("test_runner") or MCPTestRunner(TestConfig())
        return RunnerAgent(config, router, llm_client, topology, test_runner=runner)
    elif role == "critic":
        return CriticAgent(config, router, llm_client, topology)
    elif role == "manager":
        return ManagerAgent(config, router, llm_client, topology)
    else:
        raise ValueError(f"Unknown agent role: {role}")
