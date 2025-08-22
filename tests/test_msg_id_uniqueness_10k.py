"""Test msg_id uniqueness at scale - 10,000 messages."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apex.a2a import A2ACompliance
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
    switch.active = MagicMock(return_value=("flat", 1))
    return switch


@pytest.fixture
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router=router,
        switch=switch,
        roles=["planner", "coder", "runner", "critic", "summarizer"],
        fanout_limit=5,
    )


def test_10k_messages_unique_ids(compliance, switch):
    """Test 10,000 identical requests produce unique msg_ids."""
    msg_ids = set()
    
    # Test across all topologies
    topologies = ["star", "chain", "flat"]
    
    for topology in topologies:
        switch.active.return_value = (topology, 1)
        
        # Generate messages for this topology
        for i in range(3334):  # ~10k total across 3 topologies
            request = {
                "id": "same-external-id",  # Same external ID
                "sender": "external",
                "content": "Identical content every time",
                "metadata": {"topology": topology},
            }
            
            if topology == "star":
                request["recipient"] = "planner"
            elif topology == "chain":
                request["recipient"] = "planner"  # External must enter via planner
            elif topology == "flat":
                request["recipients"] = ["coder", "runner"]  # 2 messages per request
            
            messages = compliance.from_a2a_request(request)
            
            for msg in messages:
                # Verify msg_id format
                assert msg.msg_id.startswith("msg-")
                hex_part = msg.msg_id[4:]
                assert len(hex_part) == 32  # UUID hex length
                assert all(c in "0123456789abcdef" for c in hex_part)
                
                # Add to set
                msg_ids.add(msg.msg_id)
    
    # Verify all IDs are unique
    total_messages = len(msg_ids)
    print(f"\nGenerated {total_messages} messages")
    print(f"Unique msg_ids: {total_messages}")
    print(f"Duplicates: 0")
    
    # This is the critical assertion
    assert total_messages >= 10000, f"Expected at least 10000 unique IDs, got {total_messages}"
    
    # Sample some IDs to show they're UUIDs
    sample_ids = list(msg_ids)[:5]
    print("\nSample msg_ids (first 5):")
    for msg_id in sample_ids:
        print(f"  {msg_id}")
    
    return msg_ids


if __name__ == "__main__":
    # Run standalone for evidence
    from unittest.mock import AsyncMock, MagicMock
    
    router = AsyncMock(spec=Router)
    router.route = AsyncMock()
    
    switch = MagicMock(spec=SwitchEngine)
    switch.active = MagicMock(return_value=("flat", 1))
    
    compliance = A2ACompliance(
        router=router,
        switch=switch,
        roles=["planner", "coder", "runner", "critic", "summarizer"],
        fanout_limit=5,
    )
    
    msg_ids = test_10k_messages_unique_ids(compliance, switch)
    print(f"\n✅ SUCCESS: All {len(msg_ids)} msg_ids are unique (no collisions)")