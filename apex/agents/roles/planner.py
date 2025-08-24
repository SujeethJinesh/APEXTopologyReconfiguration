from __future__ import annotations

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class PlannerAgent(BaseAgent):
    """Planner agent that orchestrates the workflow."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_run_count = 0

    async def handle(self, msg: Message) -> list[Message]:
        """
        Handle incoming messages:
        - On kickoff or no tests run: create plan and send to Coder
        - On summary from Summarizer: complete the loop
        - In star topology: route messages between agents
        """
        payload = msg.payload
        topology, _ = self.switch.active()

        # Check if this is a kickoff or initial message
        if payload.get("action") == "kickoff" or self.test_run_count == 0:
            # Create a deterministic plan (no real LLM)
            plan = "Fix the bug in the add function: change subtraction to addition"
            self.test_run_count += 1

            # Send plan to Coder
            return [
                self._new_msg(
                    recipient=AgentID("coder"),
                    payload={
                        "plan": plan,
                        "target_file": "src/app.py",
                    },
                )
            ]

        # Handle summary from Summarizer
        if "summary" in payload:
            # Loop complete - could send another round or stop
            # For simplicity, we'll stop after one successful round
            return []

        # In star topology, Planner acts as hub - route to next agent
        if topology == "star" and "next_agent" in payload:
            next_agent = payload.get("next_agent")
            if next_agent:
                # Forward the message to the intended recipient
                return [
                    self._new_msg(
                        recipient=AgentID(next_agent),
                        payload=payload,
                    )
                ]

        return []
