"""Generic agents for collaborative task solving.

These agents don't have specialized roles but instead collaborate 
through discussion to solve SWE tasks together.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class GenericAgent(BaseAgent):
    """A generic agent that can collaborate with other agents to solve SWE tasks.
    
    These agents don't have fixed roles but instead discuss and collaborate
    to solve problems through message-based coordination.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f"{__name__}.GenericAgent.{self.agent_id}")
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_topology = "flat"  # Default topology
        self.role_description = ""  # Will be set based on topology
        self.task_description = ""  # Current task being worked on

    async def handle(self, msg: Message) -> List[Message]:
        """Handle incoming messages and collaborate with other agents."""
        payload = msg.payload
        msg_type = payload.get("type", "")
        
        # Record this message in conversation history
        self.conversation_history.append({
            "sender": str(msg.sender),
            "type": msg_type,
            "payload": payload
        })

        self.logger.debug(f"[{self.agent_id}] Handling message type: {msg_type}")

        # Handle topology changes first
        if msg_type == "topology_change":
            return await self._handle_topology_change(msg, payload)
        elif msg_type == "agent_initialization":
            return await self._handle_initialization(msg, payload)
        elif msg_type == "swe_task_discussion":
            return await self._handle_task_discussion(msg, payload)
        elif msg_type == "swe_collaboration_request":
            return await self._handle_collaboration_request(msg, payload)
        elif msg_type.startswith("swe_"):
            # Generic SWE message handling
            return await self._handle_swe_message(msg, payload)
        else:
            self.logger.warning(f"[{self.agent_id}] Unknown message type: {msg_type}")
            return []

    async def _handle_task_discussion(self, msg: Message, payload: Dict[str, Any]) -> List[Message]:
        """Handle task discussion messages with file operation capabilities."""
        task_id = payload.get("task_id")
        problem_statement = payload.get("problem_statement", "")
        discussion_phase = payload.get("phase", "initial")
        
        self.logger.info(f"[{self.agent_id}] Discussing task {task_id} in {discussion_phase} phase")

        # Generate a response based on our role in the discussion
        response = await self._generate_discussion_response(problem_statement, discussion_phase)
        
        # If in coding phase and we have FS access, try to perform file operations
        if discussion_phase == "coding" and self.fs:
            file_action = await self._perform_file_operation(problem_statement)
            if file_action:
                response += f"\n{file_action}"
        
        # Determine next agents to discuss with based on topology
        next_agents = self._determine_next_discussion_participants()
        
        messages = []
        for next_agent in next_agents:
            messages.append(self._new_msg(
                recipient=next_agent,
                payload={
                    "type": "swe_task_discussion",
                    "task_id": task_id,
                    "problem_statement": problem_statement,
                    "phase": discussion_phase,
                    "from_agent": str(self.agent_id),
                    "discussion_point": response,
                }
            ))
        
        return messages
    
    async def _perform_file_operation(self, problem_statement: str) -> str:
        """Perform a file operation based on the problem statement."""
        try:
            # This is a simplified example - real implementation would parse the problem
            # and determine what files need to be modified
            
            # Example: Search for files mentioned in the problem
            if "fix" in problem_statement.lower() or "bug" in problem_statement.lower():
                # Search for Python files that might contain the bug
                py_files = await self.fs.search_files(".", r"\.py$")
                if py_files and len(py_files) > 0:
                    # Try to read the first file as an example
                    first_file = py_files[0]
                    try:
                        content = await self.fs.read_file(first_file)
                        lines = content.decode('utf-8').split('\n')
                        return f"Read {first_file} ({len(lines)} lines). Ready to apply fixes."
                    except Exception as e:
                        self.logger.debug(f"Error reading file {first_file}: {e}")
                        return f"Located {len(py_files)} Python files to analyze."
            
            # Example: Create a patch if we identify a fix
            if "patch" in problem_statement.lower():
                return "Can create patches using fs.patch_file() to fix issues."
            
            return ""
            
        except Exception as e:
            self.logger.debug(f"File operation error: {e}")
            return ""

    async def _handle_collaboration_request(
        self, msg: Message, payload: Dict[str, Any]
    ) -> List[Message]:
        """Handle collaboration requests from other agents."""
        task_id = payload.get("task_id")
        collaboration_type = payload.get("collaboration_type", "general")
        # previous_discussion = payload.get("previous_discussion", "")  # For future use
        
        self.logger.info(
            f"[{self.agent_id}] Collaboration request for task {task_id}: {collaboration_type}"
        )

        # Enhanced collaboration with file operations based on phase
        response = ""
        
        if collaboration_type == "analysis" and self.fs:
            # Try to analyze the codebase structure
            response = await self._analyze_codebase()
        elif collaboration_type == "planning":
            response = f"Agent {self.agent_id}: I suggest we break this down into steps"
        elif collaboration_type == "coding" and self.fs:
            # Demonstrate file operation capability
            response = await self._demonstrate_file_operations()
        elif collaboration_type == "testing" and self.fs:
            # Search for and analyze test files
            response = await self._analyze_tests()
        else:
            response = f"Agent {self.agent_id}: I'm ready to collaborate on this task"

        # Send response back to requester
        return [self._new_msg(
            recipient=msg.sender,
            payload={
                "type": "swe_collaboration_response",
                "task_id": task_id,
                "collaboration_type": collaboration_type,
                "response": response,
                "agent_id": str(self.agent_id),
            }
        )]
    
    async def _analyze_codebase(self) -> str:
        """Analyze the codebase structure using FS operations."""
        try:
            # Search for Python files
            py_files = await self.fs.search_files(".", r"\.py$")
            num_files = len(py_files) if py_files else 0
            return (f"Agent {self.agent_id}: Found {num_files} Python files "
                    "in the repository. Ready to analyze.")
        except Exception as e:
            self.logger.debug(f"Codebase analysis error: {e}")
            return f"Agent {self.agent_id}: I can help analyze the problem"
    
    async def _demonstrate_file_operations(self) -> str:
        """Demonstrate file operation capabilities."""
        capabilities = []
        if self.fs:
            capabilities.append("read files")
            capabilities.append("write files")
            capabilities.append("patch files")
            capabilities.append("search files")
        
        if capabilities:
            return (f"Agent {self.agent_id}: I can {', '.join(capabilities)} "
                    "to implement the solution")
        return f"Agent {self.agent_id}: I can help with code implementation"
    
    async def _analyze_tests(self) -> str:
        """Analyze test files in the repository."""
        try:
            # Search for test files
            test_files = await self.fs.search_files(".", r"test.*\.py$")
            if test_files:
                return (f"Agent {self.agent_id}: Found {len(test_files)} test files. "
                        "Can analyze and fix failing tests.")
            return f"Agent {self.agent_id}: Ready to assist with test validation"
        except Exception as e:
            self.logger.debug(f"Test analysis error: {e}")
            return f"Agent {self.agent_id}: I can assist with test validation"

    async def _handle_swe_message(self, msg: Message, payload: Dict[str, Any]) -> List[Message]:
        """Handle generic SWE-related messages."""
        # For now, just acknowledge and potentially forward to other agents
        task_id = payload.get("task_id")
        
        self.logger.info(f"[{self.agent_id}] Processing SWE message for task {task_id}")
        
        # Simple acknowledgment back to sender
        return [self._new_msg(
            recipient=msg.sender,
            payload={
                "type": "swe_acknowledgment",
                "task_id": task_id,
                "message": f"Agent {self.agent_id} received and processed your message",
                "original_type": payload.get("type"),
            }
        )]

    async def _generate_discussion_response(self, problem_statement: str, phase: str) -> str:
        """Generate a discussion response using LLM with topology-aware context and file access."""
        
        # Check if we can access files for context
        file_context = ""
        if self.fs and phase in ["analysis", "coding"]:
            try:
                # Example: Try to read a relevant file if mentioned in problem statement
                # This is a simplified example - real implementation would parse problem
                if "test" in problem_statement.lower():
                    # Could search for test files
                    test_files = await self.fs.search_files(".", r"test.*\.py$")
                    if test_files:
                        file_context = f"\nFound {len(test_files)} test files in repository."
            except Exception as e:
                self.logger.debug(f"File access during discussion: {e}")
        
        # Build prompt with role context
        prompt = f"""{self.role_description}

Current task: {self.task_description or problem_statement[:500]}
Current phase: {phase}
Problem: {problem_statement[:1000]}
{file_context}

Based on your role in the {self.current_topology} topology and the current {phase} phase,
provide a specific action or insight to help solve this task. Be concise and actionable.

Response:"""
        
        # Use LLM if available
        if self.llm:
            try:
                response = await self.llm.complete(prompt=prompt, max_tokens=150)
                return f"Agent {self.agent_id}: {response.content}"
            except Exception as e:
                self.logger.warning(f"LLM generation failed: {e}")
        
        # Fallback to template responses with file awareness
        if phase == "analysis":
            if file_context:
                return (f"Agent {self.agent_id}: In {self.current_topology} topology, "
                        f"I'll analyze the problem. {file_context}")
            return (f"Agent {self.agent_id}: In {self.current_topology} topology, "
                    "I'll analyze the problem")
        elif phase == "planning":
            return (f"Agent {self.agent_id}: Following {self.current_topology} structure, "
                    "here's my plan")
        elif phase == "coding":
            if self.fs:
                return f"Agent {self.agent_id}: I can read/write files to implement the solution"
            return (f"Agent {self.agent_id}: Implementing according to "
                    f"{self.current_topology} coordination")
        else:
            return f"Agent {self.agent_id}: Working in {self.current_topology} mode"

    def _determine_next_discussion_participants(self) -> List[AgentID]:
        """Determine which agents to involve in the next discussion round based on topology."""
        topology, _ = self.switch.active()
        
        if topology == "star":
            # In star topology, route through coordinator (Agent-1 by convention)
            if str(self.agent_id) == "Agent-1":
                # Coordinator can talk to any other agent
                return [AgentID("Agent-2"), AgentID("Agent-3")]
            else:
                # Non-coordinators talk back to coordinator
                return [AgentID("Agent-1")]
        
        elif topology == "chain":
            # In chain topology, talk to next agent in sequence
            agent_num = int(str(self.agent_id).split("-")[1])
            next_num = agent_num + 1
            if next_num <= 5:  # Assume max 5 agents
                return [AgentID(f"Agent-{next_num}")]
            else:
                return []  # End of chain
        
        else:  # flat topology
            # In flat topology, can talk to any other agent
            other_agents = []
            for i in range(1, 6):  # Agents 1-5
                agent_id = AgentID(f"Agent-{i}")
                if agent_id != self.agent_id:
                    other_agents.append(agent_id)
            
            # Return up to 2 agents to avoid fanout issues
            return other_agents[:2]

    async def _handle_topology_change(self, msg: Message, payload: Dict[str, Any]) -> List[Message]:
        """Handle topology change notifications."""
        new_topology = payload.get("topology", "flat")
        agent_count = payload.get("agent_count", 5)
        task_id = payload.get("task_id")
        
        self.logger.info(f"[{self.agent_id}] Topology changed to {new_topology}")
        
        # Update topology and role
        self.current_topology = new_topology
        self.role_description = self._get_role_description(new_topology, agent_count)
        
        # Acknowledge the change
        return [self._new_msg(
            recipient=msg.sender,
            payload={
                "type": "topology_change_ack",
                "task_id": task_id,
                "agent_id": str(self.agent_id),
                "topology": new_topology,
                "role_understood": True
            }
        )]
    
    async def _handle_initialization(self, msg: Message, payload: Dict[str, Any]) -> List[Message]:
        """Handle agent initialization with task and topology context."""
        topology = payload.get("topology", "flat")
        agent_count = payload.get("agent_count", 5)
        task_description = payload.get("task_description", "")
        task_id = payload.get("task_id")
        
        # Set up agent context
        self.current_topology = topology
        self.task_description = task_description
        self.role_description = self._get_role_description(topology, agent_count)
        
        self.logger.info(f"[{self.agent_id}] Initialized for {topology} topology")
        self.logger.info(f"[{self.agent_id}] Role: {self.role_description[:100]}...")
        
        # Acknowledge initialization
        return [self._new_msg(
            recipient=msg.sender,
            payload={
                "type": "initialization_ack",
                "task_id": task_id,
                "agent_id": str(self.agent_id),
                "ready": True
            }
        )]
    
    def _get_role_description(self, topology: str, agent_count: int) -> str:
        """Get role description based on topology and agent position."""
        agent_num = int(str(self.agent_id).split("-")[1]) if "-" in str(self.agent_id) else 0
        
        if topology == "star":
            if agent_num == 1:
                return (f"""You are Agent-1, the coordinator in a star topology "
                        f"with {agent_count} agents.
You are the central hub - all other agents (Agent-2 through Agent-{agent_count}) report to you.
Your role: Delegate tasks, coordinate responses, and synthesize solutions.
You can communicate with all agents, but they can only communicate with you.""")
            else:
                return (f"""You are Agent-{agent_num}, a worker in a star topology "
                        f"with {agent_count} agents.
Agent-1 is the coordinator who will send you tasks and requests.
Your role: Execute assigned tasks and report results back to Agent-1.
You can only communicate with Agent-1, not with other worker agents.""")
        
        elif topology == "chain":
            if agent_num == 1:
                return (f"""You are Agent-1, the first agent in a chain topology "
                        f"with {agent_count} agents.
You receive the initial task and pass processed information to Agent-2.
Your role: Initial analysis and preprocessing before passing to the next agent.""")
            elif agent_num == agent_count:
                return (f"""You are Agent-{agent_num}, the final agent in a chain topology "
                        f"with {agent_count} agents.
You receive processed information from Agent-{agent_num-1} and produce the final solution.
Your role: Final synthesis and solution generation.""")
            else:
                return (f"""You are Agent-{agent_num} in a chain topology "
                        f"with {agent_count} agents.
You receive information from Agent-{agent_num-1} and pass it to Agent-{agent_num+1}.
Your role: Process and refine the information before passing it forward.""")
        
        else:  # flat topology
            return (f"""You are Agent-{agent_num} in a flat/peer topology "
                    f"with {agent_count} agents.
All agents are peers and can communicate with each other freely.
Your role: Collaborate as equals, share insights, and build consensus.
You can communicate with any agent (Agent-1 through Agent-{agent_count}).""")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the agent's conversation history."""
        return {
            "agent_id": str(self.agent_id),
            "topology": self.current_topology,
            "role": self.role_description[:100] if self.role_description else "Not initialized",
            "total_messages": len(self.conversation_history),
            "recent_messages": self.conversation_history[-5:] if self.conversation_history else [],
        }