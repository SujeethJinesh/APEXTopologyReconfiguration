from pathlib import Path


def test_claude_md_evidence_pack_sections_present():
    p = Path("claude.md")
    assert p.exists(), "claude.md missing at repo root"
    s = p.read_text(encoding="utf-8")
    assert "# APEX — Evidence Pack" in s
    assert "## M2 — Evidence Pack" in s or "## M2 — Evidence Pack (Integrations)" in s
    assert "Artifact manifest" in s
    assert "Reproduce (exact commands)" in s