from __future__ import annotations

import time
from typing import Dict
from uuid import uuid4

from apex.runtime.message import AgentID, Message
from apex.runtime.router_api import IRouter
from apex.runtime.switch_api import ISwitchEngine

from .base import BaseAgent


class EpisodeRunner:
    """
    Orchestrator for running agent episodes in tests.
    
    Initializes with agents, router, and switch engine.
    Runs episodes by:
    1. Sending kickoff to planner
    2. Looping to dequeue and handle messages
    3. Routing returned messages
    """
    
    def __init__(
        self,
        agents: Dict[AgentID, BaseAgent],
        router: IRouter,
        switch: ISwitchEngine,
    ) -> None:
        self.agents = agents
        self.router = router
        self.switch = switch
        # Get episode_id from the first agent (all should have same)
        self.episode_id = next(iter(agents.values())).episode_id if agents else str(uuid4())
    
    async def run(self, topology: str, steps: int = 50) -> dict:
        """
        Run an episode with the given topology for up to `steps` iterations.
        
        Returns a dict with counters and last summary.
        """
        # Track metrics
        messages_routed = 0
        messages_handled = 0
        last_summary = None
        step_count = 0
        
        # Initialize by enqueuing a kickoff message to planner
        _, epoch = self.switch.active()
        kickoff = Message(
            episode_id=self.episode_id,
            msg_id=uuid4().hex,
            sender=AgentID("system"),
            recipient=AgentID("planner"),
            topo_epoch=epoch,
            payload={"action": "kickoff"},
            created_ts=time.monotonic(),
        )
        await self.router.route(kickoff)
        messages_routed += 1
        
        # Main loop
        for step in range(steps):
            step_count = step + 1
            messages_in_step = 0
            
            # Process messages for each agent
            for agent_id in self.agents:
                # Dequeue message for this agent
                msg = await self.router.dequeue(agent_id)
                if msg is None:
                    continue
                
                messages_in_step += 1
                messages_handled += 1
                
                # Have the agent handle the message
                agent = self.agents[agent_id]
                returned_messages = await agent.handle(msg)
                
                # Check for summary in payload
                if "summary" in msg.payload:
                    last_summary = msg.payload["summary"]
                
                # Route all returned messages via Router (never directly delivered)
                # This enforces "Router sovereignty" - all inter-agent messages must
                # go through the Router for epoch stamping and topology validation
                for ret_msg in returned_messages:
                    await self.router.route(ret_msg)
                    messages_routed += 1
            
            # If no messages were processed in this step, check if we're done
            if messages_in_step == 0:
                # Check if there are any pending messages
                all_done = True
                for agent_id in self.agents:
                    check_msg = await self.router.dequeue(agent_id)
                    if check_msg is not None:
                        # Put it back by re-routing it
                        await self.router.route(check_msg)
                        all_done = False
                        break
                
                if all_done:
                    # Episode complete
                    break
        
        return {
            "topology": topology,
            "steps_taken": step_count,
            "messages_routed": messages_routed,
            "messages_handled": messages_handled,
            "last_summary": last_summary,
            "success": last_summary is not None and last_summary.get("status") == "success",
        }