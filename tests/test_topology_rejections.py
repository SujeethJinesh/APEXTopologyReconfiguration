from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.runtime.message import AgentID, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine
from apex.runtime.topology_guard import TopologyGuard, TopologyViolationError


@pytest.mark.asyncio
async def test_star_topology_rejection():
    """Test that star topology rejects non-planner → non-planner messages."""

    recipients = ["planner", "coder", "runner", "critic"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)
    topology_guard = TopologyGuard()

    router = Router(recipients=recipients, switch_engine=switch, topology_guard=topology_guard)
    switch._router = router

    await switch.switch_to("star")

    # Try illegal peer-to-peer message (coder → runner)
    msg = Message(
        episode_id="test_episode",
        msg_id="star_reject_001",
        sender=AgentID("coder"),
        recipient=AgentID("runner"),
        topo_epoch=1,
        payload={"test": "illegal_star_hop"},
        created_ts=0.0,
    )

    rejection_event = None
    try:
        await router.route(msg)
        assert False, "Should have rejected coder → runner in star topology"
    except TopologyViolationError as e:
        rejection_event = {
            "topology": "star",
            "event": "enqueue_rejected",
            "from_agent": str(msg.sender),
            "to_agent": str(msg.recipient),
            "msg_id": msg.msg_id,
            "reason": str(e),
        }

    assert rejection_event is not None
    print(f"✅ Star topology correctly rejected: {rejection_event['reason']}")
    return rejection_event


@pytest.mark.asyncio
async def test_chain_topology_rejection():
    """Test that chain topology rejects skip-hop messages."""

    recipients = ["planner", "coder", "runner", "critic", "summarizer"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)
    topology_guard = TopologyGuard()

    router = Router(recipients=recipients, switch_engine=switch, topology_guard=topology_guard)
    switch._router = router

    await switch.switch_to("chain")

    # Try illegal skip-hop message (coder → critic, skipping runner)
    msg = Message(
        episode_id="test_episode",
        msg_id="chain_reject_001",
        sender=AgentID("coder"),
        recipient=AgentID("critic"),
        topo_epoch=1,
        payload={"test": "illegal_chain_skip"},
        created_ts=0.0,
    )

    rejection_event = None
    try:
        await router.route(msg)
        assert False, "Should have rejected coder → critic skip in chain topology"
    except TopologyViolationError as e:
        rejection_event = {
            "topology": "chain",
            "event": "enqueue_rejected",
            "from_agent": str(msg.sender),
            "to_agent": str(msg.recipient),
            "msg_id": msg.msg_id,
            "reason": str(e),
        }

    assert rejection_event is not None
    print(f"✅ Chain topology correctly rejected: {rejection_event['reason']}")
    return rejection_event


@pytest.mark.asyncio
async def test_flat_topology_fanout_rejection():
    """Test that flat topology rejects broadcast fanout > 2."""

    recipients = ["planner", "coder", "runner", "critic", "summarizer"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)
    topology_guard = TopologyGuard()

    router = Router(recipients=recipients, switch_engine=switch, topology_guard=topology_guard)
    switch._router = router

    await switch.switch_to("flat")

    # Try illegal broadcast (fanout would be 4, exceeds limit of 2)
    msg = Message(
        episode_id="test_episode",
        msg_id="flat_reject_001",
        sender=AgentID("planner"),
        recipient=AgentID("BROADCAST"),
        topo_epoch=1,
        payload={"test": "illegal_flat_fanout"},
        created_ts=0.0,
    )

    rejection_event = None
    try:
        await router.route(msg)
        assert False, "Should have rejected broadcast fanout > 2 in flat topology"
    except TopologyViolationError as e:
        rejection_event = {
            "topology": "flat",
            "event": "enqueue_rejected",
            "from_agent": str(msg.sender),
            "to_agent": str(msg.recipient),
            "msg_id": msg.msg_id,
            "reason": str(e),
        }

    assert rejection_event is not None
    print(f"✅ Flat topology correctly rejected: {rejection_event['reason']}")
    return rejection_event


@pytest.mark.asyncio
async def test_all_topology_rejections_and_save_artifact():
    """Run all rejection tests and save JSONL artifact."""

    rejections = []

    # Run all rejection tests
    rejections.append(await test_star_topology_rejection())
    rejections.append(await test_chain_topology_rejection())
    rejections.append(await test_flat_topology_fanout_rejection())

    # Save to JSONL artifact
    artifact_path = Path("docs/A3/artifacts/topology_rejections.jsonl")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    with open(artifact_path, "w") as f:
        for rejection in rejections:
            f.write(json.dumps(rejection) + "\n")

    print(f"\n✅ Saved {len(rejections)} rejection events to {artifact_path}")

    # Verify the file is valid JSONL
    with open(artifact_path, "r") as f:
        for i, line in enumerate(f, 1):
            json.loads(line)  # Will raise if invalid

    print(f"✅ Verified: All {i} lines are valid JSON objects")
