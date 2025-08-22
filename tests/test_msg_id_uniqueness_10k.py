"""Test UUID msg_id uniqueness at scale."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from apex.a2a import A2AProtocol, A2ACompliance
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.fixture
def router():
    """Create mock router."""
    router = AsyncMock(spec=Router)
    router.route = AsyncMock()
    return router


@pytest.fixture
def switch():
    """Create mock switch."""
    switch = MagicMock(spec=SwitchEngine)
    switch.active = MagicMock(return_value=("star", 1))
    return switch


@pytest.fixture
def protocol(router, switch):
    """Create A2A protocol instance."""
    return A2AProtocol(router, switch, topology="star", planner_id="planner", fanout_limit=10)


@pytest.fixture
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router,
        switch,
        roles=["planner", "coder", "runner", "critic"],
        planner_id="planner",
        fanout_limit=10
    )


@pytest.mark.asyncio
async def test_10k_messages_unique_ids(protocol, compliance, router, switch):
    """Generate 10,000+ messages and verify all msg_ids are unique."""
    all_msg_ids = []
    
    # Test different topologies and scenarios
    test_scenarios = [
        # (topology, epoch, test_count)
        ("star", 1, 2000),
        ("chain", 2, 2000),
        ("flat", 3, 2000),
        ("star", 4, 2000),
        ("flat", 5, 2000),
    ]
    
    for topology, epoch, test_count in test_scenarios:
        switch.active.return_value = (topology, epoch)
        
        if topology == "star":
            # Generate star topology messages
            for i in range(test_count):
                await protocol.send(
                    sender="coder" if i % 2 == 0 else "runner",
                    recipient="planner" if i % 3 == 0 else "critic",
                    content=f"star-msg-{i}"
                )
        
        elif topology == "chain":
            # Generate chain topology messages
            chain_pairs = [
                ("planner", "coder"),
                ("coder", "runner"),
                ("runner", "critic"),
                ("critic", "summarizer"),
            ]
            for i in range(test_count):
                sender, recipient = chain_pairs[i % len(chain_pairs)]
                await protocol.send(
                    sender=sender,
                    recipient=recipient,
                    content=f"chain-msg-{i}"
                )
        
        elif topology == "flat":
            # Generate flat topology messages (multiple per send)
            for i in range(test_count // 3):  # Each send creates 3 messages
                await protocol.send(
                    sender="planner",
                    recipients=["coder", "runner", "critic"],
                    content=f"flat-msg-{i}"
                )
    
    # Also test ingress path with compliance layer
    ingress_scenarios = [
        ("star", 6, 1000),
        ("chain", 7, 1000),
        ("flat", 8, 1336),  # To get to at least 13,336 total
    ]
    
    for topology, epoch, test_count in ingress_scenarios:
        switch.active.return_value = (topology, epoch)
        
        if topology == "star":
            for i in range(test_count):
                request = {
                    "method": "send",
                    "params": {
                        "sender": "external" if i % 2 == 0 else "coder",
                        "recipient": "runner",
                        "content": f"ingress-star-{i}"
                    }
                }
                messages = compliance.from_a2a_request(request)
                for msg in messages:
                    all_msg_ids.append(msg.msg_id)
        
        elif topology == "chain":
            for i in range(test_count):
                request = {
                    "method": "send",
                    "params": {
                        "sender": "external",
                        "recipient": "planner",  # External must enter via planner
                        "content": f"ingress-chain-{i}"
                    }
                }
                messages = compliance.from_a2a_request(request)
                for msg in messages:
                    all_msg_ids.append(msg.msg_id)
        
        elif topology == "flat":
            for i in range(test_count // 2):  # Each creates 2 messages
                request = {
                    "method": "send",
                    "params": {
                        "sender": "broadcaster",
                        "recipients": ["coder", "runner"],
                        "content": f"ingress-flat-{i}"
                    }
                }
                messages = compliance.from_a2a_request(request)
                for msg in messages:
                    all_msg_ids.append(msg.msg_id)
    
    # Collect all msg_ids from router calls
    for call in router.route.call_args_list:
        msg = call[0][0]
        all_msg_ids.append(msg.msg_id)
    
    # Verify uniqueness
    print(f"\nGenerated {len(all_msg_ids)} messages")
    unique_ids = set(all_msg_ids)
    print(f"Unique msg_ids: {len(unique_ids)}")
    duplicates = len(all_msg_ids) - len(unique_ids)
    print(f"Duplicates: {duplicates}")
    
    # Show sample IDs
    print("\nSample msg_ids (first 5):")
    for msg_id in all_msg_ids[:5]:
        print(f"  {msg_id}")
    
    # Assert no duplicates
    assert len(unique_ids) == len(all_msg_ids), f"Found {duplicates} duplicate msg_ids!"
    
    # Verify format: msg-<32 hex chars>
    for msg_id in unique_ids:
        assert msg_id.startswith("msg-"), f"Invalid prefix in {msg_id}"
        hex_part = msg_id[4:]
        assert len(hex_part) == 32, f"Invalid length in {msg_id}: expected 32, got {len(hex_part)}"
        assert all(c in "0123456789abcdef" for c in hex_part), f"Non-hex chars in {msg_id}"
    
    # Success message
    print(f"\n✅ SUCCESS: All {len(all_msg_ids)} msg_ids are unique (no collisions)")
    assert len(all_msg_ids) >= 10000, f"Expected at least 10,000 messages, got {len(all_msg_ids)}"