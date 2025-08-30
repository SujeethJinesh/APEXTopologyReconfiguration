"""Tests for portable LLM manager with multi-instance support."""

import asyncio
import os

import pytest

# Set stub mode for testing
os.environ["APEX_LLM_STUB"] = "1"

from apex.llm.client import PortableLLMClient, StubBackend, TokenTracker
from apex.llm.manager import MultiInstanceLLMManager


# Module-level factory functions for pickling
def stub_factory(instance_id):
    """Factory function for stub backend (must be module-level for pickling)."""
    return StubBackend(instance_id)


class TestStubBackend:
    """Test the stub backend used in CI."""

    def test_stub_backend_init(self):
        """Test stub backend initialization."""
        backend = StubBackend(instance_id=0)
        assert backend.instance_id == 0
        assert not backend.ready()

    def test_stub_backend_start(self):
        """Test stub backend startup."""
        backend = StubBackend(instance_id=0)
        backend.start()
        assert backend.ready()

    def test_stub_backend_generate(self):
        """Test stub backend generation."""
        backend = StubBackend(instance_id=0)
        backend.start()

        result = backend.generate(
            session_id="test",
            prompt="write code to sort a list",
            max_new_tokens=100,
        )

        assert "text" in result
        assert "tokens_in" in result
        assert "tokens_out" in result
        assert result["finish_reason"] == "stop"
        assert "code" in result["text"].lower() or "mock" in result["text"].lower()


class TestMultiInstanceManager:
    """Test the multi-instance LLM manager."""

    @pytest.mark.asyncio
    async def test_manager_init(self):
        """Test manager initialization."""
        manager = MultiInstanceLLMManager(
            backend_factory=stub_factory,
            num_instances=2,
        )

        assert manager._num == 2
        assert not manager.ready()

    @pytest.mark.asyncio
    async def test_manager_startup(self):
        """Test manager startup and warmup."""
        manager = MultiInstanceLLMManager(
            backend_factory=stub_factory,
            num_instances=2,
        )

        # Start and warmup
        await manager.start()
        assert manager.ready()

        # Cleanup
        manager.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_generation(self):
        """Test concurrent generation from multiple instances."""
        manager = MultiInstanceLLMManager(
            backend_factory=stub_factory,
            num_instances=2,
        )

        await manager.start()

        # Generate from both instances concurrently
        results = await asyncio.gather(
            manager.generate(
                0,
                session_id="test1",
                prompt="plan a task",
                max_new_tokens=50,
            ),
            manager.generate(
                1,
                session_id="test2",
                prompt="write code",
                max_new_tokens=50,
            ),
        )

        assert len(results) == 2
        for result in results:
            assert "text" in result
            assert result["tokens_out"] > 0

        manager.shutdown()


class TestPortableLLMClient:
    """Test the portable LLM client adapter."""

    @pytest.mark.asyncio
    async def test_client_init(self):
        """Test client initialization."""
        client = PortableLLMClient()
        assert client.config.mock_mode  # Should be in mock mode for tests
        assert not client._started

    @pytest.mark.asyncio
    async def test_client_complete(self):
        """Test client completion."""
        client = PortableLLMClient()

        response = await client.complete(
            prompt="Test prompt",
            max_tokens=50,
            agent_id="Planner",
            session_id="test_session",
        )

        assert response.content != ""
        assert response.tokens_used > 0
        assert response.model == "llama_cpp_metal"  # default backend

        client.shutdown()

    @pytest.mark.asyncio
    async def test_budget_enforcement(self):
        """Test token budget enforcement."""
        tracker = TokenTracker(budget=100)  # Very small budget
        client = PortableLLMClient(token_tracker=tracker)

        # Use up budget
        tracker.record_usage(95, {})

        # Next request should be denied
        response = await client.complete(
            prompt="This is a long prompt that would use many tokens",
            max_tokens=1000,
        )

        assert response.status == "budget_denied"
        assert response.tokens_used == 0
        assert response.content == ""

        client.shutdown()

    @pytest.mark.asyncio
    async def test_agent_instance_mapping(self):
        """Test deterministic agent to instance mapping."""
        client = PortableLLMClient()

        # These should map to different instances
        agents = ["Planner", "Coder", "Runner", "Critic", "Summarizer"]
        instance_ids = []

        for agent in agents:
            instance_id = abs(hash(agent)) % client.config.num_instances
            instance_ids.append(instance_id)

        # Should have good distribution (not all same instance)
        assert len(set(instance_ids)) > 1

        client.shutdown()

    @pytest.mark.asyncio
    async def test_batch_complete(self):
        """Test batch completion."""
        client = PortableLLMClient()

        prompts = [
            "First prompt",
            "Second prompt",
            "Third prompt",
        ]

        responses = await client.batch_complete(prompts)

        assert len(responses) == 3
        for response in responses:
            assert response.content != ""
            assert response.tokens_used > 0

        client.shutdown()


class TestProgressTimeouts:
    """Test progress-aware timeout functionality."""

    def test_progress_tracker_init(self):
        """Test progress tracker initialization."""
        from apex.eval.progress import ProgressTracker

        tracker = ProgressTracker(
            episode_id="test_ep",
            episode_timeout_s=60,
            progress_extend_s=10,
        )

        assert tracker.episode_id == "test_ep"
        assert tracker.time_remaining() > 0
        assert not tracker.is_timeout()

    def test_progress_event_recording(self):
        """Test progress event recording."""
        from apex.eval.progress import ProgressEvent, ProgressTracker

        tracker = ProgressTracker(episode_id="test_ep")

        tracker.record_progress(
            ProgressEvent.FILE_WRITTEN,
            {"file": "test.py"},
        )

        assert len(tracker.events) == 1
        assert tracker.events[0]["event_type"] == "file_written"

    def test_deadline_extension(self):
        """Test deadline extension on progress."""
        from apex.eval.progress import ProgressTracker

        tracker = ProgressTracker(
            episode_id="test_ep",
            episode_timeout_s=5,  # Short timeout
            progress_extend_s=10,
            episode_timeout_max_s=20,
        )

        # Simulate near deadline
        tracker.deadline_ts = tracker.start_time + 1  # 1 second from start

        # Check extension logic
        assert tracker._should_extend_deadline()

        old_deadline = tracker.deadline_ts
        tracker._extend_deadline()

        # Should have extended
        assert tracker.deadline_ts > old_deadline
