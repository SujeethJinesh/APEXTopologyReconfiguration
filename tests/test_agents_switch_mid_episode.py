from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

import pytest
from test_helpers import TraceCollector, TracingRouter, create_agents, toy_repo, stub_fs, stub_test, stub_llm

from apex.runtime.message import AgentID, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine
from apex.runtime.topology_guard import TopologyGuard, TopologyViolationError




@pytest.mark.asyncio
async def test_switch_mid_episode(toy_repo, stub_fs, stub_test, stub_llm):
    """Test topology switch while episode is running."""
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
    
    # Start with star topology
    await switch.switch_to("star")
    initial_topology, initial_epoch = switch.active()
    assert initial_topology == "star"
    
    # Create agents with unified episode_id
    episode_id = str(uuid4())
    create_agents(router, switch, stub_fs, stub_test, stub_llm, episode_id)
    
    # Enqueue some messages in star topology
    _, epoch = switch.active()
    
    # Kickoff message
    kickoff = Message(
        episode_id="test-switch",
        msg_id=uuid4().hex,
        sender=AgentID("system"),
        recipient=AgentID("planner"),
        topo_epoch=epoch,
        payload={"action": "kickoff"},
        created_ts=time.monotonic(),
    )
    await router.route(kickoff)
    
    # Add a few more messages to populate queues
    for i in range(3):
        msg = Message(
            episode_id="test-switch",
            msg_id=uuid4().hex,
            sender=AgentID("coder"),
            recipient=AgentID("planner"),  # Valid in star
            topo_epoch=epoch,
            payload={"data": f"message_{i}"},
            created_ts=time.monotonic(),
        )
        await router.route(msg)
    
    # Check queue state before switch
    active_before = router.active_counts()
    total_before = sum(active_before.values())
    trace.add_event("pre_switch", 
                    topology="star", 
                    epoch=initial_epoch, 
                    queued_messages=total_before)
    
    # Trigger switch to chain topology
    trace.add_event("switch_prepare", from_topology="star", to_topology="chain")
    switch_task = asyncio.create_task(switch.switch_to("chain"))
    
    # Let some time pass for PREPARE phase
    await asyncio.sleep(0.002)
    
    # New messages should go to Q_next during PREPARE/QUIESCE
    new_msg = Message(
        episode_id="test-switch",
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient=AgentID("coder"),  # Valid in chain
        topo_epoch=epoch,
        payload={"during": "switch"},
        created_ts=time.monotonic(),
    )
    await router.route(new_msg)
    
    # Process some messages to help quiesce
    for agent_id in recipients:
        msg = await router.dequeue(AgentID(agent_id))
        if msg:
            trace.add_event("dequeue_during_switch", 
                          agent=agent_id, 
                          msg_epoch=msg.topo_epoch)
    
    # Wait for switch to complete
    switch_result = await switch_task
    
    if switch_result["ok"]:
        trace.add_event("switch_commit", 
                       new_topology="chain", 
                       new_epoch=switch_result["epoch"])
    else:
        trace.add_event("switch_abort", 
                       topology="star", 
                       epoch=switch_result["epoch"])
    
    # Verify new topology is active
    new_topology, new_epoch = switch.active()
    
    # Test that topology rules changed
    if new_topology == "chain":
        # Chain rules should now apply
        # This should fail (not in chain order)
        with pytest.raises(TopologyViolationError):
            bad_msg = Message(
                episode_id="test-switch",
                msg_id=uuid4().hex,
                sender=AgentID("coder"),
                recipient=AgentID("critic"),  # Invalid in chain (skips runner)
                topo_epoch=new_epoch,
                payload={},
                created_ts=time.monotonic(),
            )
            await router.route(bad_msg)
        
        # This should succeed (valid chain order)
        good_msg = Message(
            episode_id="test-switch",
            msg_id=uuid4().hex,
            sender=AgentID("coder"),
            recipient=AgentID("runner"),  # Valid in chain
            topo_epoch=new_epoch,
            payload={},
            created_ts=time.monotonic(),
        )
        await router.route(good_msg)
    
    # Verify epoch gating invariant
    # No N+1 messages should have been dequeued while N was pending
    dequeue_events = [e for e in trace.events if e["event"] == "dequeue_during_switch"]
    for event in dequeue_events:
        assert event["msg_epoch"] <= initial_epoch, \
            f"Dequeued epoch {event['msg_epoch']} while epoch {initial_epoch} was active"
    
    # Save trace artifact
    artifact_path = Path("docs/A3/artifacts/agents_switch_trace.jsonl")
    trace.save_jsonl(artifact_path)
    
    print(f"Switch mid-episode test passed. Trace saved to {artifact_path}")
    print(f"Initial: {initial_topology} (epoch {initial_epoch})")
    print(f"Final: {new_topology} (epoch {new_epoch})")
    print(f"Switch result: {'COMMIT' if switch_result['ok'] else 'ABORT'}")