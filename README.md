# APEX Framework — Milestone M0 (Scaffold + CI)

This repo is scaffolded for the APEX MVP project.

Milestone **M0** includes:
- F0.1 Scaffold (packaging, tests, linting, pre-commit, Makefile)
- F0.2 CI (GitHub Actions with lint+tests, artifact upload)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
pre-commit install
make lint
make test
```

Project uses Python 3.11. No runtime features are implemented yet (those come in later milestones).

See docs under `docs/M0`.