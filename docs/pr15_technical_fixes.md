# PR #15 Technical Fixes Complete

## All Review Feedback Addressed ✅

### A. Deterministic agent → instance mapping - FIXED ✅
**Issue:** Python's hash() is salted per process, causing unstable mappings
**Fix:** Using SHA-1 for stable hashing
**Code:** `apex/llm/client.py:269-272`
```python
h = hashlib.sha1(agent_id.encode("utf-8")).digest()
val = int.from_bytes(h[:8], "big", signed=False)
instance_id = val % self.config.num_instances
```

### B. ProcessPool initialization - FIXED ✅
**Issue:** Need spawn context and per-process model initialization
**Fix:** Already using spawn, added warmup to init_worker
**Code:** `apex/llm/manager.py:22-30`
- Forces spawn context for all platforms
- Each worker gets unique backend instance
- Warmup runs immediately on init

### C. Timeout handling - FIXED ✅
**Issue:** Need proper timeout without killing workers
**Fix:** Using asyncio.wait_for which raises TimeoutError but doesn't kill process
**Code:** `apex/llm/manager.py:169-191`
- Returns status="timeout" on timeout
- Worker continues running (result discarded)

### D. Context window clamping - FIXED ✅
**Issue:** Must prevent max_tokens exceeding context window
**Fix:** Clamp to n_ctx - prompt_tokens - 64
**Code:** `apex/llm/backends/llama_cpp_metal.py:108-117`
```python
room = self.n_ctx - prompt_tokens_est - 64
max_new_clamped = max(1, min(max_new_tokens, room))
```

### E. Token budget enforcement - FIXED ✅
**Issue:** Need conservative estimation with hard deny
**Fix:** +10% buffer, deny before executor submission
**Code:** `apex/llm/client.py:236-260`
- Conservative estimate with 10% buffer
- Hard deny returns status="budget_denied"
- No executor submission on deny

### F. Health check barrier - FIXED ✅
**Issue:** Need startup validation
**Fix:** Health check all workers, require min 3 ready
**Code:** `apex/llm/manager.py:114-142`
- Pings each worker after pool init
- Fails fast if < 3 instances ready

### G. Additional tests - FIXED ✅
**Added tests:** `tests/test_llm_parallel_isolation.py`
1. `test_budget_hard_deny` - Verifies no executor submission on budget deny
2. `test_state_isolation_with_counter` - Verifies process isolation

### H. Documentation updates - FIXED ✅
**Updated files:**
- `mvp-spec.md` - New LLM Service section with process isolation details
- `design_doc.md` - Added PortableMultiInstanceLLMManager, setup requirements, SLOs

## Test Results

```bash
APEX_LLM_STUB=1 python3 -m pytest tests/test_llm_parallel_isolation.py -xvs
```

✅ All 5 tests passing:
- test_no_cross_contamination
- test_session_isolation  
- test_concurrent_instance_distribution
- test_budget_hard_deny
- test_state_isolation_with_counter

## Smoke Test

```bash
APEX_LLM_STUB=1 python3 -m apex.llm.smoke
```

✅ 5 parallel prompts complete successfully
✅ Token tracking working
✅ No errors

## Lint Status

```bash
make lint
```

✅ ruff: All checks passed
✅ black: All files formatted

## Key Files Modified

1. `apex/llm/client.py` - SHA-1 hashing, budget enforcement
2. `apex/llm/manager.py` - Health checks, spawn context, warmup
3. `apex/llm/backends/llama_cpp_metal.py` - Context window clamping
4. `tests/test_llm_parallel_isolation.py` - New isolation tests
5. `mvp-spec.md` - Documentation updates
6. `design_doc.md` - Architecture updates

## Next Steps

1. **Place GGUF model** and set `APEX_GGUF_MODEL_PATH`
2. **Run single task smoke test:**
```bash
python -m scripts.run_eval_success_at_budget \
  --mode swe --split dev --episodes 1 \
  --policy bandit_v1 \
  --episode-timeout-s 1800 --llm-timeout-s 180 \
  --out artifacts/local/apex_bandit_1.jsonl
```
3. **Scale to N=25** for directional signal

## Commit Info

- Branch: `sujinesh/macbook_mvp_run`
- PR: #15
- Latest commit: d9d9447

All technical review items from your feedback have been addressed and tested.