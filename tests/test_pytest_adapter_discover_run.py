from pathlib import Path

import pytest

from apex.integrations.mcp.test_runner import PytestAdapter


@pytest.mark.asyncio
async def test_pytest_adapter_discover_and_run(tmp_path: Path):
    # Create a tiny test suite
    tdir = tmp_path / "proj"
    tdir.mkdir()
    (tdir / "test_example.py").write_text(
        """
def test_ok():
    assert True

def test_fail():
    assert 2 == 1
""",
        encoding="utf-8",
    )

    adapter = PytestAdapter(str(tdir))
    nodeids = await adapter.discover()
    # Should discover both tests
    assert any(n.endswith("test_example.py::test_ok") for n in nodeids)
    assert any(n.endswith("test_example.py::test_fail") for n in nodeids)

    # Run all
    res_all = await adapter.run(None, timeout_s=60)
    assert res_all["passed"] == 1
    assert res_all["failed"] == 1
    assert res_all["skipped"] == 0
    assert res_all["errors"] == 0
    assert "passed" in res_all["stdout"] or "failed" in res_all["stdout"]

    # Run selection
    sel = [next(n for n in nodeids if n.endswith("::test_ok"))]
    res_one = await adapter.run(sel, timeout_s=60)
    assert res_one["passed"] == 1
    assert res_one["failed"] == 0
