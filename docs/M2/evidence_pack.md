# Evidence Pack — M2

## Milestone: M2 — Integrations (FS/Test/LLM adapters)

## Commit(s)
- SHA: `b554cb7e147c386665619ff049d40301cf80cc52`
- Branch: `sujinesh/M2`
- PR: `#4`

## Environment
- **Python**: 3.11.13
- **OS/Arch**: Darwin x86_64 (dev), Ubuntu Linux (CI)
- **pytest**: 8.4.1
- **ruff**: 0.12.9
- **black**: 25.1.0
- **aiohttp**: 3.12.13

## Reproduce
```bash
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

# Generate artifacts:
ARTIFACTS_DIR=docs/M2/artifacts make test
```

## Artifacts
- `docs/M2/artifacts/env.json` — Environment snapshot
- `docs/M2/artifacts/junit.xml` — Structured test results (24 tests)
- `docs/M2/artifacts/pytest_stdout.txt` — Full test output

## Invariants & Checks

### M2-specific invariants:
- **FS whitelist enforced (incl. symlink protection)**: ✅ PASS
  - Evidence: `tests/test_fs_local_whitelist_patch_search.py::test_fs_search_files_ignores_symlink_escape`
  - Validates paths cannot escape root via symlinks
  
- **PytestAdapter timeout reaps process**: ✅ PASS
  - Evidence: `apex/integrations/mcp/test_runner.py:43-47`
  - Calls `proc.kill()` then `await proc.wait()` to prevent zombies
  
- **HTTPLLM retries 5xx only; no retry on 4xx**: ✅ PASS
  - Evidence: `tests/test_llm_http_client.py::test_llm_http_no_retry_on_4xx`
  - 4xx errors raise immediately without retry
  
- **Deterministic search_files() results**: ✅ PASS
  - Evidence: `apex/integrations/mcp/fs_local.py:112`
  - Results explicitly sorted

## Deviations
None. All specifications implemented as required.

## Sign-off Checklist
- [x] Artifacts present under `docs/M2/artifacts/`
- [x] All 24 tests pass (0 failures)
- [x] Invariants validated with test evidence
- [x] Security vulnerability (symlink traversal) fixed
- [x] Reliability issues (zombie processes, retry logic) addressed
- [x] Documentation updated in `docs/M2/`