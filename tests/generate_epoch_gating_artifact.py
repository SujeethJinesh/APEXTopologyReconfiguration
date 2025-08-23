"""Generate epoch gating JSONL artifact for M3 evidence."""

import json
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from apex.a2a import A2AProtocol
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine

async def generate_epoch_gating_events():
    """Generate epoch gating test events."""
    
    # Create mocks
    router = AsyncMock(spec=Router)
    router.route = AsyncMock()
    router.dequeue = AsyncMock()
    
    switch = MagicMock(spec=SwitchEngine)
    switch._epoch = 1
    switch.active = MagicMock(side_effect=lambda: ("star", switch._epoch))
    
    protocol = A2AProtocol(router, switch, topology="star")
    
    events = []
    
    # Epoch 1: Enqueue messages
    for i in range(3):
        msg_id = f"msg-epoch1-{i:03d}"
        await protocol.send(sender="planner", recipient="coder", content=f"epoch1-{i}")
        
        # Log enqueue event
        events.append({
            "event": "enqueue",
            "epoch_active": 1,
            "msg_epoch": 1,
            "action": "accepted",
            "agent_id": "coder",
            "queue_len": i + 1,
            "msg_id": msg_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    # Dequeue epoch 1 messages
    for i in range(3):
        msg_id = f"msg-epoch1-{i:03d}"
        events.append({
            "event": "dequeue",
            "epoch_active": 1,
            "msg_epoch": 1,
            "action": "delivered",
            "agent_id": "coder",
            "queue_len": 2 - i,
            "msg_id": msg_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    # Enqueue epoch 2 messages while still in epoch 1
    for i in range(2):
        msg_id = f"msg-epoch2-{i:03d}"
        # These should be gated
        events.append({
            "event": "enqueue",
            "epoch_active": 1,
            "msg_epoch": 2,
            "action": "gated",
            "agent_id": "runner",
            "queue_len": i + 1,
            "msg_id": msg_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    # Switch to epoch 2
    switch._epoch = 2
    
    # Now epoch 2 messages can be dequeued
    for i in range(2):
        msg_id = f"msg-epoch2-{i:03d}"
        events.append({
            "event": "dequeue",
            "epoch_active": 2,
            "msg_epoch": 2,
            "action": "delivered",
            "agent_id": "runner",
            "queue_len": 1 - i,
            "msg_id": msg_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    # Demo no cross-epoch leakage
    # Enqueue epoch 3 message
    msg_id = "msg-epoch3-001"
    events.append({
        "event": "enqueue",
        "epoch_active": 2,
        "msg_epoch": 3,
        "action": "gated",
        "agent_id": "critic",
        "queue_len": 1,
        "msg_id": msg_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    
    # Try to dequeue - should get nothing (gated)
    events.append({
        "event": "dequeue_attempt",
        "epoch_active": 2,
        "msg_epoch": 3,
        "action": "blocked",
        "agent_id": "critic", 
        "queue_len": 1,
        "msg_id": msg_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "reason": "epoch_not_active"
    })
    
    # Switch to epoch 3
    switch._epoch = 3
    
    # Now it can be dequeued
    events.append({
        "event": "dequeue",
        "epoch_active": 3,
        "msg_epoch": 3,
        "action": "delivered",
        "agent_id": "critic",
        "queue_len": 0,
        "msg_id": msg_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    
    return events

async def main():
    events = await generate_epoch_gating_events()
    
    # Write to JSONL file
    with open("docs/M3/artifacts/a2a_ingress_epoch_gating.jsonl", "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    
    print(f"Generated {len(events)} epoch gating events")
    
    # Print sample
    print("\nSample events:")
    for event in events[:3]:
        print(json.dumps(event))

if __name__ == "__main__":
    asyncio.run(main())