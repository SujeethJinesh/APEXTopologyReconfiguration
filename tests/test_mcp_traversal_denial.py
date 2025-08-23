"""Test MCP server enforces path traversal denial."""

import importlib.util
import os
import tempfile
from pathlib import Path

import pytest

HAS_FASTMCP = importlib.util.find_spec("fastmcp") is not None


@pytest.mark.skipif(not HAS_FASTMCP, reason="FastMCP not installed")
class TestMCPTraversalDenial:
    """Test MCP server blocks directory traversal attempts."""

    @pytest.mark.asyncio
    async def test_fs_read_blocks_traversal(self):
        """Test fs_read cannot escape whitelist via traversal."""
        from apex.mcp.fastmcp_server import APEXMCPServer

        # Create temp workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            safe_dir = Path(tmpdir) / "safe"
            safe_dir.mkdir()
            safe_file = safe_dir / "allowed.txt"
            safe_file.write_text("safe content")

            # Create server with whitelist
            server = APEXMCPServer(whitelist=[str(safe_dir)])

            # Attempt various traversal patterns
            traversal_attempts = [
                "../../../etc/passwd",
                "../../etc/shadow",
                "/etc/hosts",
            ]

            for path in traversal_attempts:
                with pytest.raises(PermissionError) as exc_info:
                    await server.fs.read_file(path)

                # Verify error message indicates denial
                assert "escapes whitelist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fs_write_blocks_traversal(self):
        """Test fs_write cannot escape whitelist."""
        from apex.mcp.fastmcp_server import APEXMCPServer

        with tempfile.TemporaryDirectory() as tmpdir:
            safe_dir = Path(tmpdir) / "safe"
            safe_dir.mkdir()

            server = APEXMCPServer(whitelist=[str(safe_dir)])

            # Attempt to write outside whitelist
            traversal_paths = [
                "../evil.txt",
                "/tmp/evil.txt",
                "../../etc/cron.d/evil",
            ]

            for path in traversal_paths:
                with pytest.raises(PermissionError) as exc_info:
                    await server.fs.write_file(path, b"malicious content")

                error_msg = str(exc_info.value)
                assert "escapes whitelist" in error_msg or "outside" in error_msg

    @pytest.mark.asyncio
    async def test_symlink_traversal_blocked(self):
        """Test symlinks cannot be used to escape whitelist."""
        from apex.mcp.fastmcp_server import APEXMCPServer

        with tempfile.TemporaryDirectory() as tmpdir:
            safe_dir = Path(tmpdir) / "safe"
            safe_dir.mkdir()

            # Create a symlink that points outside
            evil_link = safe_dir / "evil_link"
            evil_link.symlink_to("/etc/passwd")

            server = APEXMCPServer(whitelist=[str(safe_dir)])

            # Attempt to read through symlink
            with pytest.raises(PermissionError) as exc_info:
                await server.fs.read_file("evil_link")

            assert "escapes whitelist" in str(exc_info.value) or "outside" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_respects_whitelist(self):
        """Test search_files stays within whitelist."""
        from apex.mcp.fastmcp_server import APEXMCPServer

        with tempfile.TemporaryDirectory() as tmpdir:
            safe_dir = Path(tmpdir) / "safe"
            safe_dir.mkdir()

            # Create test files
            (safe_dir / "test1.txt").write_text("content 1")
            (safe_dir / "test2.txt").write_text("content 2")

            # Create file outside safe_dir
            outside_file = Path(tmpdir) / "outside.txt"
            outside_file.write_text("should not find")

            server = APEXMCPServer(whitelist=[str(safe_dir)])

            # Search should only find files in safe_dir (use relative path from root)
            results = await server.fs.search_files(".", "content")

            # The search returns paths relative to the root, verify we got expected files
            # Sort for deterministic comparison
            results_sorted = sorted(results)
            assert len(results_sorted) == 2
            assert "test1.txt" in results_sorted[0]
            assert "test2.txt" in results_sorted[1]

    def test_default_transport_is_stdio(self):
        """Test MCP server defaults to stdio transport."""
        from apex.mcp.fastmcp_server import APEXMCPServer

        server = APEXMCPServer()

        # The default run() should use stdio
        # We can verify by checking the method signature or docs
        import inspect

        run_signature = inspect.signature(server.run)
        params = run_signature.parameters

        # Check default value for transport parameter
        assert "transport" in params
        assert params["transport"].default == "stdio"

    @pytest.mark.asyncio
    async def test_mcp_server_stdio_not_network(self):
        """Test MCP server with stdio doesn't open network ports."""
        from unittest.mock import AsyncMock, patch

        from apex.mcp.fastmcp_server import APEXMCPServer

        # When run with stdio, it should not bind to any network port
        # This is a property test - stdio means no network binding
        # We verify by checking that run(transport="stdio") doesn't call network methods

        # FastMCP may not have these exact method names, so mock at a higher level
        with patch("apex.mcp.fastmcp_server.FastMCP") as MockFastMCP:
            mock_instance = MockFastMCP.return_value
            mock_instance.run_stdio = AsyncMock()
            mock_instance.run_http = AsyncMock()

            # Create a new server with mocked FastMCP
            server2 = APEXMCPServer()
            server2.mcp = mock_instance

            # Enable the server flag
            os.environ["APEX_MCP_SERVER"] = "1"

            # Run with stdio (default)
            await server2.run(transport="stdio")

            # Should call stdio, not http
            mock_instance.run_stdio.assert_called_once()
            mock_instance.run_http.assert_not_called()

            # Clean up
            os.environ.pop("APEX_MCP_SERVER", None)
