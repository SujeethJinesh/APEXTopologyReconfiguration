"""Integration test for MVP runtime."""

import pytest

from apex.harness import APEXHarness, EpisodeConfig
from apex.llm.client import LLMConfig


class TestMVPIntegration:
    """Test complete MVP runtime integration."""

    @pytest.mark.asyncio
    async def test_static_star_episode(self):
        """Test episode execution with static star topology."""
        # Create harness with mock LLM
        harness = APEXHarness(llm_config=LLMConfig(mock_mode=True), workspace_dir="/tmp/apex_test")

        # Configure episode
        config = EpisodeConfig(
            task_id="test_1",
            task_description="Write a function to compute factorial",
            topology="star",
            max_iterations=5,
            token_budget=1000,
        )

        # Run episode
        result = await harness.run_episode(config)

        # Verify result structure
        assert result.task_id == "test_1"
        assert isinstance(result.success, bool)
        assert result.tokens_used >= 0
        assert result.elapsed_seconds > 0
        assert result.iterations > 0
        assert len(result.topology_switches) == 0  # Static topology

    @pytest.mark.asyncio
    async def test_dynamic_topology_episode(self):
        """Test episode with dynamic topology switching."""
        harness = APEXHarness(
            llm_config=LLMConfig(mock_mode=True), workspace_dir="/tmp/apex_test_dynamic"
        )

        config = EpisodeConfig(
            task_id="test_2",
            task_description="Debug and fix the sorting algorithm",
            topology="dynamic",
            max_iterations=10,
            token_budget=2000,
        )

        result = await harness.run_episode(config)

        # Verify dynamic behavior
        assert result.task_id == "test_2"
        assert result.tokens_used >= 0  # May be 0 in mock mode
        # May or may not have switches depending on bandit decisions
        assert isinstance(result.topology_switches, list)

    @pytest.mark.asyncio
    async def test_token_budget_enforcement(self):
        """Test that token budget is enforced."""
        harness = APEXHarness(
            llm_config=LLMConfig(mock_mode=True), workspace_dir="/tmp/apex_test_budget"
        )

        # Normal budget
        config = EpisodeConfig(
            task_id="test_3",
            task_description="Complex task requiring many tokens",
            topology="star",
            max_iterations=100,
            token_budget=10000,  # Normal budget
        )

        result = await harness.run_episode(config)

        # Should complete normally
        assert result.iterations <= 100
        # Token tracking works
        assert result.tokens_used > 0
        # Budget was respected (didn't exceed)
        assert harness.token_tracker.remaining() >= 0

    @pytest.mark.asyncio
    async def test_batch_episodes(self):
        """Test batch episode execution."""
        harness = APEXHarness(
            llm_config=LLMConfig(mock_mode=True), workspace_dir="/tmp/apex_test_batch"
        )

        # Create multiple episodes
        episodes = [
            EpisodeConfig(
                task_id=f"batch_{i}",
                task_description=f"Task {i}",
                topology="star" if i % 2 == 0 else "chain",
                max_iterations=3,
            )
            for i in range(3)
        ]

        # Run batch
        results = await harness.run_batch(episodes, parallel=1)

        # Verify all completed
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.task_id == f"batch_{i}"
            assert result.iterations > 0
