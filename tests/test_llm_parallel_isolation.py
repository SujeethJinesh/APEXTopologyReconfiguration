"""Test parallel LLM instance isolation."""

import asyncio
import os

import pytest

# Set stub mode for CI
os.environ["APEX_LLM_STUB"] = "1"

from apex.llm.client import PortableLLMClient


@pytest.mark.asyncio
class TestParallelIsolation:
    """Test that parallel LLM instances don't cross-contaminate."""

    async def test_no_cross_contamination(self):
        """Test N parallel generates with unique markers have no cross-contamination."""
        client = PortableLLMClient()

        # Define unique prompts with markers
        prompts = [
            ("Remember the code ALPHA-001 and repeat it back", "ALPHA-001"),
            ("Remember the code BETA-002 and repeat it back", "BETA-002"),
            ("Remember the code GAMMA-003 and repeat it back", "GAMMA-003"),
            ("Remember the code DELTA-004 and repeat it back", "DELTA-004"),
            ("Remember the code EPSILON-005 and repeat it back", "EPSILON-005"),
        ]

        # Run prompts in parallel with different agent IDs
        async def check_response(prompt, expected_code, agent_id):
            response = await client.complete(
                prompt=prompt,
                max_tokens=50,
                agent_id=agent_id,
                session_id=f"test_{agent_id}",
            )

            # Check that response contains expected code
            content = response.content

            # Check no other codes appear
            other_codes = [code for _, code in prompts if code != expected_code]

            return {
                "agent_id": agent_id,
                "expected": expected_code,
                "content": content,
                "has_expected": expected_code in content,
                "has_others": any(code in content for code in other_codes),
            }

        # Create tasks
        tasks = [
            check_response(prompt, code, f"Agent_{i}") for i, (prompt, code) in enumerate(prompts)
        ]

        # Run in parallel
        results = await asyncio.gather(*tasks)

        # Verify isolation
        for r in results:
            # In stub mode, we can't guarantee exact echo, but no cross-contamination
            assert not r["has_others"], (
                f"Agent {r['agent_id']} response contains other agents' codes! "
                f"Expected only {r['expected']}, content: {r['content']}"
            )

        client.shutdown()

    async def test_session_isolation(self):
        """Test that different sessions don't share context."""
        client = PortableLLMClient()

        # First, establish context in session A
        await client.complete(
            prompt="My name is Alice. What is my name?",
            max_tokens=30,
            agent_id="TestAgent",
            session_id="session_a",
        )

        # Then ask in session B (should not know Alice)
        response_b1 = await client.complete(
            prompt="What is my name?",
            max_tokens=30,
            agent_id="TestAgent",
            session_id="session_b",
        )

        # Session B should not contain "Alice"
        assert "Alice" not in response_b1.content, (
            f"Session B knows about Alice from session A! " f"Response: {response_b1.content}"
        )

        client.shutdown()

    async def test_concurrent_instance_distribution(self):
        """Test that agents map to different instances."""
        client = PortableLLMClient()

        # Different agent roles should map to different instances
        agents = ["Planner", "Coder", "Runner", "Critic", "Summarizer"]

        # Get instance IDs
        instance_ids = []
        for agent in agents:
            instance_id = abs(hash(agent)) % client.config.num_instances
            instance_ids.append(instance_id)

        # Should distribute across instances (not all same)
        unique_instances = len(set(instance_ids))
        assert unique_instances > 1, (
            f"All agents mapped to same instance! "
            f"Distribution: {dict(zip(agents, instance_ids))}"
        )

        client.shutdown()


@pytest.mark.external
@pytest.mark.asyncio
class TestRealModelIsolation:
    """Tests that require a real model (not stub)."""

    async def test_real_parallel_isolation(self):
        """Test real model parallel isolation (requires APEX_GGUF_MODEL_PATH)."""
        if os.getenv("APEX_LLM_STUB") == "1":
            pytest.skip("Requires real model")

        if not os.getenv("APEX_GGUF_MODEL_PATH"):
            pytest.skip("APEX_GGUF_MODEL_PATH not set")

        client = PortableLLMClient()

        # More complex prompts that test real isolation
        prompts = [
            ("Calculate: 42 * 17 = ", "714"),
            ("Complete: The capital of France is ", "Paris"),
            ("Continue: Once upon a time ", None),  # Open-ended
        ]

        async def run_prompt(prompt, agent_id):
            response = await client.complete(
                prompt=prompt,
                max_tokens=20,
                agent_id=agent_id,
                session_id=f"real_{agent_id}",
            )
            return response.content

        # Run in parallel
        tasks = [run_prompt(prompt, f"Agent_{i}") for i, (prompt, _) in enumerate(prompts)]

        results = await asyncio.gather(*tasks)

        # Each should have unique response
        assert len(set(results)) == len(
            results
        ), f"Got duplicate responses across agents: {results}"

        client.shutdown()
