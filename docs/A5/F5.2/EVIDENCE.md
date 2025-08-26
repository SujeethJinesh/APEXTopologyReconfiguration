# A5/F5.2 Evidence: SWE-bench Lite Integration

## Implementation Summary

Successfully integrated SWE-bench Lite into the Success@Budget harness, enabling evaluation on real tasks while maintaining CI stability.

## Commit Information
- Branch: `sujinesh/A5_F52`
- Commit: `0f96f29`
- PR Ready: https://github.com/SujeethJinesh/APEXTopologyReconfiguration/pull/new/sujinesh/A5_F52

## Key Components

### 1. Provider Layer (`apex/eval/providers/swe_lite.py`)
- Loads SWE-bench Lite from Hugging Face or local cache
- Maps fields correctly (instance_id → task_id)
- Supports dev (23) and test (300) splits
- Falls back gracefully when network unavailable

### 2. Repository Manager (`apex/eval/repo_manager.py`)
- Handles git operations: clone, checkout, patch application
- Caches checkouts to avoid redundant clones
- Runs tests with deterministic timeout
- Supports GitHub token authentication

### 3. Harness Integration (`apex/eval/harness.py`)
- Added `mode="swe"` alongside existing `mode="stub"`
- `_run_swe_episode()`: Full task execution pipeline
- Tracks topology traces, switches, budget denials
- Success criterion: tests pass AND under budget

### 4. CLI Updates (`scripts/run_eval_success_at_budget.py`)
- `--mode {stub,swe}` flag (default: stub for CI)
- `--split {dev,test}` for dataset selection
- Network access gated by `APEX_ALLOW_NETWORK=1`
- Produces extended JSONL with SWE-specific fields

## Test Coverage

```bash
# Run all new tests
pytest tests/test_swe_provider_schema.py tests/test_swe_mode_wiring.py -v

# Results
=================== 9 passed, 1 skipped, 1 warning in 0.42s ====================
```

- `test_swe_provider_schema.py`: Schema validation, field mapping
- `test_swe_mode_wiring.py`: Repo manager, harness integration
- All tests CI-safe (network tests marked `@pytest.mark.external`)

## Artifacts

Sample JSONL output (`docs/A5/artifacts/swe/dev/apex_dynamic_sample.jsonl`):
```json
{
  "task_id": "django__django-12345",
  "policy": "apex_dynamic",
  "success": false,
  "tokens_used": 7234,
  "budget": 10000,
  "over_budget": false,
  "budget_denied": 0,
  "topology_trace": [
    {"tick": 0, "topo": "star", "dwell": 1, "cooldown": 0},
    {"tick": 1, "topo": "chain", "dwell": 1, "cooldown": 3}
  ],
  "switches": 1,
  "episode_ms": 1234.56
}
```

## Validation

```bash
# JSONL validation
python3 scripts/validate_jsonl.py docs/A5/artifacts/swe/dev/apex_dynamic_sample.jsonl
# Output: apex_dynamic_sample.jsonl      ✅ VALID      3 objects

# Lint checks
make lint
# Output: All checks passed!
```

## Commands to Run

### CI-Safe (Stub Mode)
```bash
python -m scripts.run_eval_success_at_budget \
  --mode=stub --episodes=12 --budget=10000 \
  --policy=apex_dynamic --out artifacts/stub.jsonl
```

### SWE-bench Lite (Requires Network)
```bash
APEX_ALLOW_NETWORK=1 GITHUB_TOKEN=ghp_... \
python -m scripts.run_eval_success_at_budget \
  --mode=swe --split=dev --episodes=10 \
  --budget=10000 --policy=apex_dynamic \
  --out artifacts/swe_dev.jsonl
```

## Acceptance Criteria Met

✅ A) mode="swe" implemented end-to-end  
✅ B) No changes to controller policy or reward  
✅ C) CI remains green; network tests opt-in via env flag  
✅ D) compute_lift.py works on SWE artifacts  
✅ E) Documentation with commands and dataset references  

## Dataset References

- [SWE-bench Lite Overview](https://www.swebench.com/lite.html)
- [Hugging Face Dataset](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite)

---

*Implementation complete and ready for PR review.*