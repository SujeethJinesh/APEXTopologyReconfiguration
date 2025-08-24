from __future__ import annotations

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class SummarizerAgent(BaseAgent):
    """Summarizer agent that creates final reports."""

    async def handle(self, msg: Message) -> list[Message]:
        """
        Handle incoming messages:
        - From Critic: build summary and send back to Planner
        """
        payload = msg.payload

        # Build summary JSON
        summary = {
            "tests_passed": payload.get("passed", 0),
            "tests_failed": payload.get("failed", 0),
            "files_touched": ["src/app.py"],
            "coder_action": payload.get("coder_action"),
            "status": "success" if payload.get("failed", 0) == 0 else "failure",
        }

        # Always send back to Planner (valid in all topologies)
        return [
            self._new_msg(
                recipient=AgentID("planner"),
                payload={
                    "summary": summary,
                },
            )
        ]
