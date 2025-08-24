from __future__ import annotations

import time
from pathlib import Path
from typing import List
from uuid import uuid4

import pytest
from test_helpers import (
    TraceCollector,
    TracingRouter,
    create_agents,
)

from apex.agents.base import BaseAgent
from apex.agents.episode import EpisodeRunner
from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine
from apex.runtime.topology_guard import TopologyGuard, TopologyViolationError


class TracingEpisodeRunner(EpisodeRunner):
    """Episode runner that traces agent handle events."""

    def __init__(self, *args, trace_collector: TraceCollector, **kwargs):
        super().__init__(*args, **kwargs)
        self.trace = trace_collector

    async def run(self, topology: str, steps: int = 50) -> dict:
        """Run episode with tracing."""
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

                # Trace handle event
                self.trace.add_event(
                    "handle",
                    epoch=epoch,
                    topology=topology,
                    agent=str(agent_id),
                    action=msg.payload.get("action", "process"),
                )

                # Have the agent handle the message
                agent = self.agents[agent_id]
                returned_messages = await agent.handle(msg)

                # Check for summary in payload
                if "summary" in msg.payload:
                    last_summary = msg.payload["summary"]

                # Route all returned messages
                for ret_msg in returned_messages:
                    await self.router.route(ret_msg)
                    messages_routed += 1

            # If no messages were processed in this step, we're done
            if messages_in_step == 0:
                break

        return {
            "topology": topology,
            "steps_taken": step_count,
            "messages_routed": messages_routed,
            "messages_handled": messages_handled,
            "last_summary": last_summary,
            "success": last_summary is not None and last_summary.get("status") == "success",
        }


class MulticastAgent(BaseAgent):
    """Agent that tries to send to multiple recipients (for testing fanout)."""

    async def handle(self, msg: Message) -> List[Message]:
        """Try to send to 3 recipients to test fanout limit."""
        # Attempt to send to 3 different agents (exceeds fanout limit of 2)
        return [
            self._new_msg(AgentID("coder"), {"test": "multicast"}),
            self._new_msg(AgentID("runner"), {"test": "multicast"}),
            self._new_msg(AgentID("critic"), {"test": "multicast"}),
        ]


@pytest.mark.asyncio
async def test_flat_topology_end_to_end(toy_repo, stub_fs, stub_test, stub_llm):
    """Test flat topology with all agents."""
    trace = TraceCollector()

    # Create router with topology guard (fanout limit = 2)
    recipients = ["planner", "coder", "runner", "critic", "summarizer"]
    topology_guard = TopologyGuard(fanout_limit=2)

    # Create switch engine
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)

    # Create tracing router with switch and guard
    router = TracingRouter(
        recipients=recipients,
        trace_collector=trace,
        switch_engine=switch,
        topology_guard=topology_guard,
    )

    # Update switch to use tracing router
    switch._router = router

    # Set topology to flat
    await switch.switch_to("flat")

    # Create agents with unified episode_id
    episode_id = str(uuid4())
    agents = create_agents(router, switch, stub_fs, stub_test, stub_llm, episode_id)

    # Create and run episode
    runner = TracingEpisodeRunner(
        agents=agents,
        router=router,
        switch=switch,
        trace_collector=trace,
    )

    result = await runner.run("flat", steps=20)

    # Assertions
    assert result["success"], "Episode should succeed with tests passing"
    assert result["steps_taken"] <= 20, "Should complete in <= 20 steps"

    # In flat topology, all peer-to-peer messages are allowed
    # Verify that various P2P messages work
    test_pairs = [
        ("coder", "runner"),
        ("runner", "critic"),
        ("critic", "coder"),
        ("planner", "summarizer"),
    ]

    for sender, recipient in test_pairs:
        test_msg = Message(
            episode_id="test",
            msg_id=uuid4().hex,
            sender=AgentID(sender),
            recipient=AgentID(recipient),
            topo_epoch=Epoch(1),
            payload={"test": "p2p"},
            created_ts=time.monotonic(),
        )
        # Should not raise in flat topology
        await router.route(test_msg)

    # Test fanout limit enforcement
    # Create a multicast agent that tries to send to >2 recipients
    multicast_agent = MulticastAgent(
        agent_id=AgentID("multicast_test"),
        router=router,
        switch=switch,
        fs=stub_fs,
        test=stub_test,
        episode_id=episode_id,  # Add required episode_id
        llm=stub_llm,
    )

    # Try to send messages exceeding fanout
    test_msg = Message(
        episode_id="test",
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient=AgentID("multicast_test"),
        topo_epoch=Epoch(1),
        payload={"test": "fanout"},
        created_ts=time.monotonic(),
    )

    messages = await multicast_agent.handle(test_msg)
    assert len(messages) == 3, "Should try to send 3 messages"

    # Router should allow first 2 but could reject 3rd if broadcast used
    # For unicast, all 3 should work since they're separate route calls
    sent_count = 0
    for msg in messages:
        try:
            await router.route(msg)
            sent_count += 1
        except TopologyViolationError:
            pass

    # In our implementation, unicast messages don't trigger fanout check
    # Only BROADCAST would trigger it
    # Let's test BROADCAST fanout
    broadcast_msg = Message(
        episode_id="test",
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient="BROADCAST",
        topo_epoch=Epoch(1),
        payload={"test": "broadcast"},
        created_ts=time.monotonic(),
    )

    # BROADCAST to 4 agents (5 total - 1 sender) exceeds fanout of 2
    with pytest.raises(TopologyViolationError):
        await router.route(broadcast_msg)

    # Save trace artifact
    artifact_path = Path("docs/A3/artifacts/agents_flat_trace.jsonl")
    trace.save_jsonl(artifact_path)

    print(f"Flat topology test passed. Trace saved to {artifact_path}")
    print(f"Episode completed in {result['steps_taken']} steps")
    print(f"Messages routed: {result['messages_routed']}")
    print(f"Messages handled: {result['messages_handled']}")
