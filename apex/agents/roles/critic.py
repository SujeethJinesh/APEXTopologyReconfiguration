from __future__ import annotations

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class CriticAgent(BaseAgent):
    """Critic agent that evaluates test results."""

    async def handle(self, msg: Message) -> list[Message]:
        """
        Handle incoming messages:
        - From Runner: evaluate test results
        - If failed > 0: send feedback to Coder
        - If all pass: send to Summarizer
        """
        payload = msg.payload
        failed = payload.get("failed", 0)
        passed = payload.get("passed", 0)

        # Check topology to determine recipient
        topology, _ = self.switch.active()

        if failed > 0:
            # Tests are failing, send feedback to Coder
            # Deterministic suggestion
            feedback = "Tests are still failing. Ensure the add function returns a + b, not a - b."

            if topology == "star":
                # In star, must go through planner
                recipient = AgentID("planner")
            elif topology == "chain":
                # In chain, would need to go back through the chain
                # Since chain is unidirectional, send to planner to restart
                recipient = AgentID("planner")
            else:
                # In flat, direct peer-to-peer is allowed
                recipient = AgentID("coder")

            return [
                self._new_msg(
                    recipient=recipient,
                    payload={
                        "feedback": feedback,
                        "target_file": "src/app.py",
                        "test_results": {
                            "passed": passed,
                            "failed": failed,
                        },
                        "next_agent": "coder",  # Hint for planner
                    },
                )
            ]
        else:
            # All tests pass, send to Summarizer
            if topology == "star":
                # In star, must go through planner
                recipient = AgentID("planner")
            elif topology == "chain":
                # In chain, critic -> summarizer is valid
                recipient = AgentID("summarizer")
            else:
                # In flat, direct peer-to-peer is allowed
                recipient = AgentID("summarizer")

            return [
                self._new_msg(
                    recipient=recipient,
                    payload={
                        "passed": passed,
                        "failed": failed,
                        "coder_action": payload.get("coder_action"),
                        "next_agent": "summarizer",  # Hint for planner
                    },
                )
            ]
