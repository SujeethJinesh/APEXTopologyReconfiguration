from __future__ import annotations

from uuid import uuid4

import pytest
from test_helpers import create_agents, toy_repo, stub_fs, stub_test, stub_llm

from apex.agents.episode import EpisodeRunner
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine
from apex.runtime.topology_guard import TopologyGuard


@pytest.mark.asyncio
async def test_unified_episode_id(toy_repo, stub_fs, stub_test, stub_llm):
    """Test that all messages in an episode share the same episode_id."""
    
    # Create router with topology guard
    recipients = ["planner", "coder", "runner", "critic", "summarizer"]
    topology_guard = TopologyGuard()
    
    # Create switch engine
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)
    
    # Track all messages
    routed_messages = []
    
    class MessageCapturingRouter(Router):
        """Router that captures all routed messages."""
        
        async def route(self, msg):
            routed_messages.append(msg)
            return await super().route(msg)
    
    # Create capturing router with switch and guard
    router = MessageCapturingRouter(
        recipients=recipients,
        switch_engine=switch,
        topology_guard=topology_guard,
    )
    
    # Update switch to use capturing router
    switch._router = router
    
    # Set topology to star
    await switch.switch_to("star")
    
    # Create agents with unified episode_id
    episode_id = str(uuid4())
    agents = create_agents(router, switch, stub_fs, stub_test, stub_llm, episode_id)
    
    # Create and run episode
    runner = EpisodeRunner(
        agents=agents,
        router=router,
        switch=switch,
    )
    
    result = await runner.run("star", steps=20)
    
    # Verify episode succeeded
    assert result["success"], "Episode should succeed"
    
    # Verify all messages have the same episode_id
    assert len(routed_messages) > 0, "Should have routed messages"
    
    episode_ids = set(msg.episode_id for msg in routed_messages)
    assert len(episode_ids) == 1, f"All messages should share same episode_id, found: {episode_ids}"
    
    # Verify the episode_id matches what we created
    assert episode_id in episode_ids, f"Episode ID should match created ID {episode_id}"
    
    # Also verify all agents have the same episode_id
    agent_episode_ids = set(agent.episode_id for agent in agents.values())
    assert len(agent_episode_ids) == 1, "All agents should have same episode_id"
    assert episode_id in agent_episode_ids, "Agents should have the created episode_id"
    
    print(f"✅ Test passed: All {len(routed_messages)} messages share episode_id: {episode_id}")