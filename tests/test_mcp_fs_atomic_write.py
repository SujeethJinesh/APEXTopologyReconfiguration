"""Test atomic write operations with rollback for MCP FS wrapper."""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

from apex.integrations.mcp.fs_local import LocalFS


@pytest_asyncio.fixture
async def fs():
    """Create LocalFS instance with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fs = LocalFS(tmpdir)
        yield fs


@pytest.mark.asyncio
async def test_atomic_replace_no_partial_on_failure(fs):
    """Test that atomic write rolls back on failure, leaving no partial file."""
    # Create a file with original content
    test_file = "test.txt"
    original_content = b"original content"
    await fs.write_file(test_file, original_content)
    
    # Verify original content
    content = await fs.read_file(test_file)
    assert content == original_content
    
    # Monkeypatch os.replace to fail
    with patch("os.replace") as mock_replace:
        mock_replace.side_effect = OSError("Simulated replace failure")
        
        # Try to write new content - should fail
        new_content = b"new content that should not persist"
        with pytest.raises(OSError, match="Simulated replace failure"):
            await fs.write_file(test_file, new_content)
    
    # Verify original content is still intact (no partial write)
    content = await fs.read_file(test_file)
    assert content == original_content, "Original file was corrupted on failed write"
    
    # Verify no temp files left behind
    root_path = Path(fs._root)
    temp_files = list(root_path.glob(".test.txt.*.tmp"))
    assert len(temp_files) == 0, f"Temp files not cleaned up: {temp_files}"


@pytest.mark.asyncio
async def test_patch_is_atomic(fs):
    """Test that patch_file is atomic and rolls back on failure."""
    # Create a file with content A
    test_file = "patch_test.txt"
    content_a = "Hello world, this is content A"
    await fs.write_file(test_file, content_a.encode())
    
    # Verify initial content
    content = await fs.read_file(test_file)
    assert content.decode() == content_a
    
    # Try to patch with a failure during replace
    with patch("os.replace") as mock_replace:
        mock_replace.side_effect = OSError("Simulated patch failure")
        
        diff = """--- a/patch_test.txt
+++ b/patch_test.txt
@@
- content A
+ content B
@@"""
        
        with pytest.raises(OSError, match="Simulated patch failure"):
            await fs.patch_file(test_file, diff)
    
    # Verify content is still A (no partial patch)
    content = await fs.read_file(test_file)
    assert content.decode() == content_a, "File was corrupted during failed patch"
    
    # Now do a successful patch
    diff = """--- a/patch_test.txt
+++ b/patch_test.txt
@@
- content A
+ content B
@@"""
    
    await fs.patch_file(test_file, diff)
    
    # Verify content is now B
    content = await fs.read_file(test_file)
    expected = "Hello world, this is content B"
    assert content.decode() == expected, "Successful patch did not apply"


@pytest.mark.asyncio
async def test_concurrent_writes_are_safe(fs):
    """Test that concurrent writes don't corrupt files."""
    test_file = "concurrent.txt"
    
    # Write initial content
    await fs.write_file(test_file, b"initial")
    
    # Perform multiple concurrent writes
    async def write_content(data: bytes):
        await fs.write_file(test_file, data)
        return data
    
    # Launch concurrent writes
    tasks = [
        write_content(f"content-{i}".encode())
        for i in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Read final content
    final_content = await fs.read_file(test_file)
    
    # Final content should be one of the written values (not corrupted)
    assert final_content in results, "File content corrupted by concurrent writes"
    
    # Verify no temp files left
    root_path = Path(fs._root)
    temp_files = list(root_path.glob(".concurrent.txt.*.tmp"))
    assert len(temp_files) == 0, f"Temp files not cleaned up: {temp_files}"


@pytest.mark.asyncio
async def test_write_creates_parent_directories(fs):
    """Test that write_file creates parent directories atomically."""
    # Write to nested path that doesn't exist
    nested_file = "deep/nested/dir/file.txt"
    content = b"nested content"
    
    await fs.write_file(nested_file, content)
    
    # Verify file was created with content
    read_content = await fs.read_file(nested_file)
    assert read_content == content
    
    # Verify directory structure exists
    root_path = Path(fs._root)
    assert (root_path / "deep" / "nested" / "dir").exists()


@pytest.mark.asyncio
async def test_fsync_ensures_durability(fs):
    """Test that fsync is called to ensure durability."""
    test_file = "durable.txt"
    
    # Mock os.fsync to verify it's called
    with patch("os.fsync") as mock_fsync:
        await fs.write_file(test_file, b"durable content")
        
        # Verify fsync was called (ensures data is on disk)
        assert mock_fsync.called, "fsync not called - data may not be durable"


@pytest.mark.asyncio
async def test_atomic_write_flow_logging():
    """Generate evidence of atomic write flow for documentation."""
    import json
    from datetime import datetime
    
    events = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        fs = LocalFS(tmpdir)
        test_file = "atomic_test.txt"
        
        # Log atomic write flow
        events.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": "atomic_write_start",
            "file": test_file,
            "action": "create_temp_file"
        })
        
        # Patch to log temp file creation
        original_mkstemp = tempfile.mkstemp
        
        def logged_mkstemp(*args, **kwargs):
            fd, tmppath = original_mkstemp(*args, **kwargs)
            events.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "operation": "temp_file_created",
                "temp_path": os.path.basename(tmppath),
                "fd": fd
            })
            return fd, tmppath
        
        with patch("tempfile.mkstemp", side_effect=logged_mkstemp):
            # Patch os.replace to log
            original_replace = os.replace
            
            def logged_replace(src, dst):
                events.append({
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "operation": "atomic_rename",
                    "source": os.path.basename(src),
                    "target": os.path.basename(dst),
                    "action": "os.replace"
                })
                return original_replace(src, dst)
            
            with patch("os.replace", side_effect=logged_replace):
                # Perform atomic write
                await fs.write_file(test_file, b"atomic content")
        
        events.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operation": "atomic_write_complete",
            "file": test_file,
            "result": "success"
        })
        
        # Verify file exists
        content = await fs.read_file(test_file)
        assert content == b"atomic content"
    
    # Write evidence
    with open("docs/M3/artifacts/fs_atomicity_evidence.jsonl", "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    
    print(f"Generated {len(events)} atomic flow events")
    return events


if __name__ == "__main__":
    # Run the logging test to generate evidence
    asyncio.run(test_atomic_write_flow_logging())