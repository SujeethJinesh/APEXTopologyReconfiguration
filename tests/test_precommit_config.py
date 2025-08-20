from pathlib import Path


def test_precommit_config_has_expected_hooks():
    p = Path(".pre-commit-config.yaml")
    assert p.exists(), "missing .pre-commit-config.yaml"
    s = p.read_text()
    for hook in ("black", "ruff", "isort", "end-of-file-fixer"):
        assert hook in s, f"expected hook {hook} in pre-commit config"
