#!/usr/bin/env python3
"""Simple test to verify MCP integration works."""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

from apex.agents.message_swe_agent import MessageSWEAgent
from apex.integrations.mcp.fs_local import LocalFS
from apex.runtime.message import AgentID
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


async def test_basic_mcp():
    """Test basic MCP operations."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Testing in: {tmpdir}")
        
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def test():\n    pass\n")
        
        # Initialize FS
        fs = LocalFS(root=tmpdir)
        
        # Test read
        print("\n1. Testing file read...")
        content = await fs.read_file("test.py")
        print(f"   ✓ Read {len(content)} bytes")
        assert b"def test" in content
        
        # Test write
        print("\n2. Testing file write...")
        await fs.write_file("new.py", b"# New file\nprint('hello')\n")
        print("   ✓ Created new.py")
        
        # Verify write
        new_content = await fs.read_file("new.py")
        assert b"hello" in new_content
        print("   ✓ Verified new file content")
        
        # Test patch
        print("\n3. Testing file patch...")
        diff = """--- a/test.py
+++ b/test.py
@@
- pass
+ return 'patched'
@@"""
        await fs.patch_file("test.py", diff)
        
        # Verify patch
        patched = await fs.read_file("test.py")
        assert b"patched" in patched
        print("   ✓ File patched successfully")
        
        # Test search (searches file CONTENTS, not names)
        print("\n4. Testing file search (content-based)...")
        matches = await fs.search_files(".", "hello")
        print(f"   ✓ Found {len(matches)} files containing 'hello': {matches}")
        assert len(matches) == 1
        
        return True


async def test_agents_with_mcp():
    """Test that agents have MCP access."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\n5. Testing agents with MCP...")
        
        # Initialize components
        router = Router()
        switch = SwitchEngine(router=router)
        fs = LocalFS(root=tmpdir)
        episode_id = str(uuid4())
        
        # Create MessageSWEAgent
        agent = MessageSWEAgent(
            agent_id=AgentID("swe_agent"),
            router=router,
            switch=switch,
            fs=fs,
            episode_id=episode_id,
            llm=None,
        )
        
        # Verify generic agents have FS
        print(f"   - Created {len(agent.generic_agents)} generic agents")
        for agent_id, generic_agent in agent.generic_agents.items():
            assert generic_agent.fs is not None
            print(f"   ✓ {agent_id} has FS access")
        
        return True


async def test_sandboxing():
    """Test sandboxing."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\n6. Testing sandboxing...")
        
        fs = LocalFS(root=tmpdir)
        
        # Try to escape
        try:
            await fs.read_file("../../etc/passwd")
            print("   ❌ Sandbox escape worked (BAD)")
            return False
        except PermissionError:
            print("   ✓ Sandbox escape blocked")
        
        return True


async def main():
    """Run all tests."""
    print("=" * 50)
    print("MCP Integration Test")
    print("=" * 50)
    
    try:
        success = True
        success &= await test_basic_mcp()
        success &= await test_agents_with_mcp()
        success &= await test_sandboxing()
        
        if success:
            print("\n" + "=" * 50)
            print("✅ ALL TESTS PASSED")
            print("=" * 50)
        else:
            print("\n❌ Some tests failed")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())