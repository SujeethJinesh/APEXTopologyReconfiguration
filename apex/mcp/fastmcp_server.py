"""FastMCP server wrapper for APEX Framework integrations.

Exposes FS and Test adapters as MCP tools for interoperability.
Off by default, enabled via APEX_MCP_SERVER environment variable.
"""

import asyncio
import os
from typing import Optional

# Guard imports for optional FastMCP
try:
    from fastmcp import FastMCP

    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    FastMCP = None

from apex.integrations.mcp.fs_local import LocalFS
from apex.integrations.mcp.test_runner import PytestAdapter


class APEXMCPServer:
    """FastMCP server exposing APEX integrations as MCP tools."""

    def __init__(self, whitelist: Optional[list[str]] = None):
        """Initialize MCP server.

        Args:
            whitelist: Allowed paths for FS operations

        Raises:
            RuntimeError: If FastMCP not installed
        """
        if not HAS_FASTMCP:
            raise RuntimeError(
                "FastMCP not available. Install with: pip install 'apex-framework[mcp]'"
            )

        self.mcp = FastMCP("apex-tools")
        self.whitelist = whitelist or ["/tmp", "/workspace"]

        # Initialize adapters (LocalFS takes root, not whitelist)
        # Use the first whitelist path as root
        self.fs = LocalFS(root=self.whitelist[0])
        # PytestAdapter needs a working directory
        self.test = PytestAdapter(workdir=".")

        # Register tools
        self._register_fs_tools()
        self._register_test_tools()

    def _register_fs_tools(self):
        """Register filesystem tools with MCP."""

        @self.mcp.tool()
        async def fs_read(path: str) -> str:
            """Read file contents.

            Args:
                path: File path to read

            Returns:
                str: File contents
            """
            return await self.fs.read(path)

        @self.mcp.tool()
        async def fs_write(path: str, data: str) -> bool:
            """Write data to file.

            Args:
                path: File path to write
                data: Data to write

            Returns:
                bool: Success status
            """
            await self.fs.write(path, data)
            return True

        @self.mcp.tool()
        async def fs_patch(path: str, diff: str) -> bool:
            """Apply unified diff patch to file.

            Args:
                path: File to patch
                diff: Unified diff string

            Returns:
                bool: Success status
            """
            result = await self.fs.patch(path, diff)
            return result.get("success", False)

        @self.mcp.tool()
        async def fs_search(root: str, regex: str) -> list[str]:
            """Search files by content regex.

            Args:
                root: Root directory to search
                regex: Regular expression pattern

            Returns:
                list[str]: Matching file paths (sorted)
            """
            results = await self.fs.search_files(root, regex)
            return results.get("files", [])

    def _register_test_tools(self):
        """Register test runner tools with MCP."""

        @self.mcp.tool()
        async def test_discover() -> list[str]:
            """Discover available tests.

            Returns:
                list[str]: Test IDs
            """
            result = await self.test.discover()
            return result.get("tests", [])

        @self.mcp.tool()
        async def test_run(selected: Optional[list[str]] = None, timeout_s: int = 120) -> dict:
            """Run tests with optional selection.

            Args:
                selected: Test IDs to run (None = all)
                timeout_s: Timeout in seconds

            Returns:
                dict: Test results with passed/failed/errors
            """
            return await self.test.run(selected=selected, timeout_s=timeout_s)

    async def run(self, transport: str = "stdio"):
        """Run MCP server.

        Args:
            transport: Transport type (stdio or http)
        """
        if not os.environ.get("APEX_MCP_SERVER"):
            return

        if transport == "stdio":
            # Run with stdio transport for local/test use
            await self.mcp.run_stdio()
        elif transport == "http":
            # Run HTTP server
            await self.mcp.run_http(host="127.0.0.1", port=10002)
        else:
            raise ValueError(f"Unknown transport: {transport}")


async def main():
    """Entry point for standalone MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="APEX MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type",
    )
    parser.add_argument(
        "--whitelist",
        nargs="+",
        default=["/tmp", "/workspace"],
        help="Allowed paths for FS operations",
    )
    args = parser.parse_args()

    # Force enable for standalone run
    os.environ["APEX_MCP_SERVER"] = "1"

    server = APEXMCPServer(whitelist=args.whitelist)
    await server.run(transport=args.transport)


if __name__ == "__main__":
    asyncio.run(main())
