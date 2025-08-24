from __future__ import annotations

from apex.agents.base import BaseAgent
from apex.runtime.message import AgentID, Message


class RunnerAgent(BaseAgent):
    """Runner agent that executes tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.discovered_tests = None

    async def handle(self, msg: Message) -> list[Message]:
        """
        Handle incoming messages:
        - From Coder: run tests and send results to Critic
        """
        # Discover tests if not already done
        if self.discovered_tests is None:
            self.discovered_tests = await self.test.discover()

        # Run all tests with timeout
        test_results = await self.test.run(tests=None, timeout_s=60)

        # Extract pass/fail counts
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)
        failing_tests = test_results.get("failures", [])

        # Check topology to determine recipient
        topology, _ = self.switch.active()

        if topology == "star":
            # In star, must go through planner
            recipient = AgentID("planner")
        elif topology == "chain":
            # In chain, runner -> critic is valid
            recipient = AgentID("critic")
        else:
            # In flat, direct peer-to-peer is allowed
            recipient = AgentID("critic")

        # Send results to appropriate recipient
        return [
            self._new_msg(
                recipient=recipient,
                payload={
                    "passed": passed,
                    "failed": failed,
                    "failing_tests": failing_tests,
                    "coder_action": msg.payload.get("coder_action"),
                    "next_agent": "critic",  # Hint for planner in star topology
                },
            )
        ]
