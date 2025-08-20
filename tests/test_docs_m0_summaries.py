from pathlib import Path


def test_docs_m0_summaries_present():
    paths = [
        Path("docs/M0/F0.1/T0.1_summary.md"),
        Path("docs/M0/F0.2/T0.2_summary.md"),
    ]
    for p in paths:
        assert p.exists(), f"missing {p}"
        content = p.read_text()
        assert "What" in content and "How" in content and "Why" in content

    s = Path("docs/M0/F0.1/T0.1_summary.md").read_text()
    for token in ("DoD", "make lint", "make test"):
        assert token in s
