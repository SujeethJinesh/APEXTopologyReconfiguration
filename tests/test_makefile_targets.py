from pathlib import Path


def test_makefile_targets_and_tools():
    p = Path("Makefile")
    assert p.exists()
    s = p.read_text()
    assert "lint:" in s
    assert "fmt:" in s
    assert "test:" in s
    assert "ruff" in s
    assert "black" in s
    assert "pytest" in s
