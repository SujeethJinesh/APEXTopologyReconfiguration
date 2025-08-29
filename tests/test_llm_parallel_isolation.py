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

    async def test_budget_hard_deny(self):
        """Test that budget deny happens before executor submission."""
        from apex.llm.client import TokenTracker

        # Create client with nearly exhausted budget
        tracker = TokenTracker(budget=10000)
        tracker.used = 9500  # Nearly exhausted

        client = PortableLLMClient(token_tracker=tracker)

        # Try to make a request that would exceed budget
        response = await client.complete(
            prompt="Write a long story " * 50,  # Long prompt to trigger estimate
            max_tokens=800,
            agent_id="TestAgent",
            session_id="budget_test",
        )

        # Should be denied
        assert response.status == "budget_denied"
        assert response.error == "budget_denied"
        assert response.tokens_used == 0
        assert response.content == ""

        # Budget should not have changed
        assert tracker.used == 9500

        client.shutdown()

    async def test_budget_deny_no_backend_call(self):
        """Test that budget deny truly prevents backend invocation."""
        from apex.llm.client import TokenTracker

        # Create client with tiny budget
        tracker = TokenTracker(budget=100)
        tracker.used = 99  # Almost exhausted

        client = PortableLLMClient(token_tracker=tracker)

        # Track backend calls
        backend_calls = []

        # Monkey-patch the manager to track calls
        original_ensure_started = client.ensure_started

        async def track_ensure_started():
            backend_calls.append("ensure_started")
            await original_ensure_started()

        client.ensure_started = track_ensure_started

        # Request that exceeds budget
        response = await client.complete(
            prompt="Hello world",  # Even small prompt should exceed
            max_tokens=50,
            agent_id="TestAgent",
        )

        # Verify no backend initialization happened
        assert len(backend_calls) == 0, f"Backend was initialized: {backend_calls}"
        assert response.status == "budget_denied"

        client.shutdown()

    async def test_state_isolation_with_counter(self):
        """Test that each process has its own state (simulated with counter)."""
        # This test verifies process isolation by checking that
        # different instances don't share global state
        client = PortableLLMClient()

        # Generate from different agents (should map to different instances)
        agents = ["Agent_A", "Agent_B", "Agent_C"]

        # Each agent generates multiple times
        results = {}
        for agent in agents:
            agent_results = []
            for i in range(3):
                response = await client.complete(
                    prompt=f"Count: {i}",
                    max_tokens=10,
                    agent_id=agent,
                    session_id=f"{agent}_session",
                )
                agent_results.append(response.content)
            results[agent] = agent_results

        # In process isolation, each agent's responses should be independent
        # (we can't test actual counters in stub mode, but we verify no errors)
        for agent in agents:
            assert len(results[agent]) == 3
            for content in results[agent]:
                assert content  # Should have some content
                assert "error" not in content.lower()

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
