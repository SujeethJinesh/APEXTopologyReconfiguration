# APEX — Evidence Pack

This document is the single source of truth for milestone evidence (artifacts, commands, invariant checks, and sign‑off state). For each milestone, we attach the artifact manifest, exact commands, and links/paths needed to reproduce and verify.

---

## M2 — Evidence Pack (Integrations)

**Commit(s):** `b554cb7e147c386665619ff049d40301cf80cc52`, branch: `sujinesh/M2`, PR: `#4`  
**CI run(s):** GitHub Actions `ci.yml` for the commit above  
**Changed paths (diffstat):** apex/integrations/**; tests/**; docs/M2/**; pyproject.toml

**Environment (dev & CI):**
- Python: `3.11.13`  
- OS/Arch: `Darwin x86_64` (dev), `Ubuntu Linux` (CI)  
- Tools: `pytest 8.4.1`, `ruff 0.12.9`, `black 25.1.0`, `aiohttp 3.12.13`

### Reproduce (exact commands)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
# Produce artifacts for M2:
ARTIFACTS_DIR=artifacts/M2 make test
```

### Artifact manifest

- `artifacts/M2/env.json` — environment snapshot (python, os, tool versions)
- `artifacts/M2/pytest_stdout.txt` — full pytest output
- `artifacts/M2/junit.xml` — structured test results

### Invariants & checks (M2)

- **FS whitelist enforced (incl. symlink protection):** PASS — tests/test_fs_local_whitelist_patch_search.py
- **PytestAdapter timeout reaps process:** PASS — tests/test_pytest_adapter_discover_run.py
- **HTTPLLM retries 5xx only; no retry on 4xx; timeouts bubble:** PASS — tests/test_llm_http_client.py
- **Deterministic search_files() results:** PASS

### Deviations from spec

None.

### Risk & SLO impact

- **Security:** traversal mitigated by symlink/resolve guards.
- **Reliability:** zombie prevention on timeout verified.

### Sign‑off checklist

- [ ] Artifacts present under `artifacts/M2/`
- [ ] Tests pass on CI; JUnit attached
- [ ] Invariants validated with evidence paths
- [ ] Docs updated

---

## Template — Evidence Pack for future milestones

**Milestone:** M{m} — <title>  
**Commit(s):** <sha(s)>, branch: <branch>, PR: #<n>  
**CI run(s):** <workflow/run ids or links>

### Reproduce (exact commands)
```bash
pip install -e ".[dev]"
ARTIFACTS_DIR=artifacts/M{m} make test
# For evals/benchmarks (when applicable):
# python -m scripts.run_eval_success_at_budget ... --out artifacts/M{m}/eval.jsonl
```

### Artifact manifest

- `artifacts/M{m}/env.json`
- `artifacts/M{m}/pytest_stdout.txt`, `artifacts/M{m}/junit.xml`
- (When applicable) `.../eval.jsonl`, `.../hist_bins.json`, `.../metrics.json`
- (Optional) `coverage.xml`

### Invariants & checks

- **I1 At‑least‑once & idempotency** — evidence/tests
- **I2 Causal monotonicity across epochs** — evidence/tests
- **I3 Per‑pair FIFO within epoch** — evidence/tests
- **I4 Budget safety** — evidence/tests (when BudgetGuard lands)
- **I5 Health fallback** — evidence/tests (when added)

### SLOs (when applicable)

- Success@Budget lift vs Best Static (paired bootstrap CI)
- Budget violations (CP bound)
- Controller p95; Switch p95 (phases)
- Stress loss; epoch‑check cost; memory; pooling benefit; PlanCache hit rate

### Recompute formulas

- **p95 from histogram:** Sum counts until ≥0.95·N; return bucket's upper edge.
- **Clopper‑Pearson (one‑sided 95%):** BetaInv(0.95, v+1, n−v)
- **Paired bootstrap lift:** Resample tasks with replacement; compute APEX−BestStatic per sample; report 2.5/97.5 percentiles.

### Deviations / Open questions

…

### Sign‑off checklist

- [ ] Artifacts complete & reproducible
- [ ] Invariants verified with pointers
- [ ] SLOs met (or deltas explained)