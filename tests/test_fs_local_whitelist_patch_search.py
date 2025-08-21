from pathlib import Path

import pytest

from apex.integrations.mcp.fs_local import LocalFS


@pytest.mark.asyncio
async def test_fs_whitelist_read_write_and_escape(tmp_path: Path):
    fs = LocalFS(str(tmp_path))
    await fs.write_file("a/b.txt", b"content")
    data = await fs.read_file("a/b.txt")
    assert data == b"content"

    # Attempt to escape the whitelist
    with pytest.raises(PermissionError):
        await fs.write_file("../escape.txt", b"x")


@pytest.mark.asyncio
async def test_fs_patch_minimal_unified_diff(tmp_path: Path):
    fs = LocalFS(str(tmp_path))
    await fs.write_file("file.txt", b"hello world")
    diff = """--- a/file.txt
+++ b/file.txt
@@
- world
+ APEX
@@
"""
    await fs.patch_file("file.txt", diff)
    data = await fs.read_file("file.txt")
    assert data.decode("utf-8") == "hello APEX"


@pytest.mark.asyncio
async def test_fs_search_files_content_regex(tmp_path: Path):
    fs = LocalFS(str(tmp_path))
    await fs.write_file("x.txt", b"hay hay")
    await fs.write_file("y.txt", b"hay needle hay")
    matches = await fs.search_files(".", r"needle")
    assert matches == ["y.txt"]


@pytest.mark.asyncio
async def test_fs_search_files_ignores_symlink_escape(tmp_path, tmp_path_factory):
    """Test that search_files does not follow symlinks that escape the whitelist."""
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("needle", encoding="utf-8")

    fs_root = tmp_path / "root"
    fs_root.mkdir()

    # Best-effort: create symlink inside root -> outside file
    try:
        (fs_root / "link.txt").symlink_to(outside / "secret.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    fs = LocalFS(str(fs_root))
    matches = await fs.search_files(".", r"needle")
    assert matches == [], "must not read through symlink to outside"
