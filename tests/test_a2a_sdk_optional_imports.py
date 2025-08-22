"""Tests for A2A SDK optional imports and functionality."""

import importlib.util

import pytest


HAS_A2A = importlib.util.find_spec("a2a") is not None or importlib.util.find_spec("python_a2a") is not None
HAS_UVICORN = importlib.util.find_spec("uvicorn") is not None


@pytest.mark.skipif(not HAS_A2A, reason="A2A SDK not installed")
class TestA2ASDKImports:
    """Test A2A SDK imports work correctly when installed."""

    def test_sdk_imports_correctly(self):
        """Test A2A SDK can be imported with correct module name."""
        # This should work if a2a-sdk is installed
        try:
            import a2a
            assert a2a is not None
            module_name = "a2a"
        except ImportError:
            import python_a2a as a2a
            assert a2a is not None
            module_name = "python_a2a"

        # Verify key classes are available
        assert hasattr(a2a, "AgentCard") or hasattr(a2a, "agent_card")
        print(f"A2A SDK imported successfully as: {module_name}")

    def test_compliance_layer_uses_sdk(self):
        """Test A2ACompliance detects and uses SDK when available."""
        from apex.a2a import sdk_adapter

        # Should have detected the SDK
        assert sdk_adapter.HAS_A2A_SDK is True, "SDK not detected despite being installed"

        # AgentCard should be the real class, not None
        assert sdk_adapter.AgentCard is not None

    def test_agent_card_with_sdk(self):
        """Test agent card generation works with SDK."""
        from apex.a2a import A2ACompliance
        from apex.runtime.router import Router
        from apex.runtime.switch import SwitchEngine
        from unittest.mock import MagicMock

        router = MagicMock(spec=Router)
        switch = MagicMock(spec=SwitchEngine)
        switch.active = MagicMock(return_value=("star", 1))

        compliance = A2ACompliance(
            router=router,
            switch=switch,
            roles=["planner", "coder", "runner", "critic"],
        )

        card = compliance.agent_card()

        # Should return a proper dict with SDK structure
        assert isinstance(card, dict)
        assert "name" in card
        assert card["name"] == "apex-framework"
        assert "capabilities" in card
        assert "endpoints" in card

        # SDK-specific structure checks
        if "capabilities" in card:
            caps = card["capabilities"]
            # With SDK, capabilities might be nested differently
            assert "roles" in caps or "multi-role" in str(caps)


@pytest.mark.skipif(not HAS_UVICORN, reason="uvicorn not installed")
class TestA2AHTTPIngress:
    """Test A2A HTTP ingress server functionality."""

    def test_uvicorn_available(self):
        """Test uvicorn can be imported for HTTP ingress."""
        import uvicorn
        assert uvicorn is not None
        assert hasattr(uvicorn, "Config")
        assert hasattr(uvicorn, "Server")

    @pytest.mark.asyncio
    async def test_ingress_start_with_sdk(self):
        """Test ingress server can be started when SDK is available."""
        import os
        from unittest.mock import AsyncMock, MagicMock, patch

        # Mock the SDK availability check
        with patch("apex.a2a.sdk_adapter.HAS_A2A_HTTP", True):
            with patch("apex.a2a.sdk_adapter.create_ingress_app") as mock_create_app:
                mock_create_app.return_value = MagicMock()  # Mock app
                
                from apex.a2a import A2AProtocol
                from apex.runtime.router import Router
                from apex.runtime.switch import SwitchEngine

                router = AsyncMock(spec=Router)
                switch = MagicMock(spec=SwitchEngine)
                switch.active = MagicMock(return_value=("star", 1))

                protocol = A2AProtocol(router, switch)

                # Enable ingress via env
                os.environ["APEX_A2A_INGRESS"] = "1"

                # Mock uvicorn to avoid actual server start
                with patch("uvicorn.Server") as mock_server_class:
                    mock_server = AsyncMock()
                    mock_server_class.return_value = mock_server
                    mock_server.serve = AsyncMock()

                    # This should not raise if SDK is properly installed
                    await protocol.start_ingress(port=10001)

                    # Verify server was configured
                    mock_server_class.assert_called_once()

                # Cleanup
                os.environ.pop("APEX_A2A_INGRESS", None)


@pytest.mark.skipif(HAS_A2A, reason="Testing fallback when SDK not installed")
class TestA2AFallback:
    """Test A2A functionality falls back gracefully without SDK."""

    def test_compliance_fallback_without_sdk(self):
        """Test A2ACompliance works without SDK using dict fallback."""
        from unittest.mock import MagicMock

        # Force reload without SDK
        import apex.a2a.sdk_adapter as sdk_adapter
        from apex.runtime.router import Router
        from apex.runtime.switch import SwitchEngine

        # Temporarily force HAS_A2A_SDK to False to test fallback
        original_has_sdk = sdk_adapter.HAS_A2A_SDK
        sdk_adapter.HAS_A2A_SDK = False

        try:
            router = MagicMock(spec=Router)
            switch = MagicMock(spec=SwitchEngine)
            switch.active = MagicMock(return_value=("star", 1))

            compliance = sdk_adapter.A2ACompliance(
                router=router,
                switch=switch,
                roles=["planner", "coder", "runner", "critic"],
            )

            card = compliance.agent_card()

            # Should return a fallback dict
            assert isinstance(card, dict)
            assert card["name"] == "apex-framework"
            assert "capabilities" in card
            assert card["capabilities"]["roles"] == ["planner", "coder", "runner", "critic"]

        finally:
            # Restore original value
            sdk_adapter.HAS_A2A_SDK = original_has_sdk