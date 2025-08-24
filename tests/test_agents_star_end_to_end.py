from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import pytest
from test_helpers import (
    TraceCollector,
    TracingRouter,
    create_agents,
)

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


@pytest.mark.asyncio
async def test_star_topology_end_to_end(toy_repo, stub_fs, stub_test, stub_llm):
    """Test star topology with all agents."""
    trace = TraceCollector()

    # Create router with topology guard
    recipients = ["planner", "coder", "runner", "critic", "summarizer"]
    topology_guard = TopologyGuard()

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

    # Set topology to star
    await switch.switch_to("star")

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

    result = await runner.run("star", steps=20)

    # Assertions
    assert result["success"], "Episode should succeed with tests passing"
    assert result["steps_taken"] <= 20, "Should complete in <= 20 steps"

    # Verify star topology rules from trace
    # All non-planner sends should be to planner
    non_planner_sends = [
        e
        for e in trace.events
        if e["event"] == "enqueue" and e["from_agent"] != "planner" and e["from_agent"] != "system"
    ]
    for event in non_planner_sends:
        assert (
            event["to_agent"] == "planner"
        ), f"Non-planner {event['from_agent']} must send to planner"

    # Test Router guard rejection of illegal hop
    with pytest.raises(TopologyViolationError):
        illegal_msg = Message(
            episode_id="test",
            msg_id=uuid4().hex,
            sender=AgentID("coder"),
            recipient=AgentID("runner"),  # Illegal: non-planner to non-planner
            topo_epoch=Epoch(1),
            payload={},
            created_ts=time.monotonic(),
        )
        await router.route(illegal_msg)

    # Save trace artifact
    artifact_path = Path("docs/A3/artifacts/agents_star_trace.jsonl")
    trace.save_jsonl(artifact_path)

    print(f"Star topology test passed. Trace saved to {artifact_path}")
    print(f"Episode completed in {result['steps_taken']} steps")
    print(f"Messages routed: {result['messages_routed']}")
    print(f"Messages handled: {result['messages_handled']}")
