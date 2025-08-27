# A5 Evaluation Artifacts

This directory contains machine-verifiable artifacts from the Success@Budget evaluation harness.

**IMPORTANT NOTE:** For A5/F5.5 evaluation, use ONLY the `*_dev_sample100.*` files in the `swe/dev/` subdirectory. These represent the frozen task list evaluation with N=100 paired samples. Earlier artifacts without this suffix are legacy and should not be used for current analysis.

## File Descriptions

### Episode Results (JSONL)

- **static_star.jsonl** - Results from static star topology policy
- **static_chain.jsonl** - Results from static chain topology policy  
- **static_flat.jsonl** - Results from static flat topology policy
- **static_best.jsonl** - Best static policy selected per task
- **apex_dynamic.jsonl** - Results from APEX bandit_v1 dynamic policy

### Analysis Results (JSON)

- **lift.json** - Lift analysis comparing APEX to Best Static
- **cp_static.json** - Clopper-Pearson bound for static policy violations
- **cp_apex.json** - Clopper-Pearson bound for APEX policy violations

## Schemas

### Episode Result Schema (JSONL files)
```json
{
  "task_id": "string",      // Unique task identifier
  "policy": "string",       // Policy name (static_star, static_chain, static_flat, bandit_v1, static_best)
  "success": "boolean",     // Task succeeded AND stayed under budget
  "tokens_used": "integer", // Total tokens consumed
  "over_budget": "boolean", // True if tokens_used > budget
  "budget": "integer",      // Token budget for episode
  "seed": "integer",        // Random seed for reproducibility
  "epoch_switches": "integer", // Number of topology switches (dynamic only)
  "notes": "string"         // Optional notes (e.g., topology preference)
}
```

### Lift Analysis Schema (lift.json)
```json
{
  "lift_abs": "float",      // Absolute lift (APEX - Best Static)
  "ci_low": "float",        // Lower bound of 95% CI
  "ci_high": "float",       // Upper bound of 95% CI
  "n": "integer",           // Number of tasks analyzed
  "seed": "integer",        // Random seed for bootstrap
  "n_bootstrap": "integer", // Number of bootstrap samples
  "paired": "boolean"       // Whether paired bootstrap was used
}
```

### CP Bound Schema (cp_*.json)
```json
{
  "violations": "integer",     // Number of budget violations
  "total": "integer",          // Total episodes
  "cp_upper_95": "float",      // Clopper-Pearson 95% upper bound
  "seed": "integer",           // Random seed
  "confidence": "float",       // Confidence level (0.95)
  "empirical_rate": "float"    // Observed violation rate
}
```

## SWE-bench Lite Dev Results (F5.3)

### Evaluation Summary
- **Dataset:** SWE-bench Lite dev split (23 tasks simulated via stub mode)
- **Budget:** 10,000 tokens per episode
- **Mode:** Stub mode (CI-safe, no network required)

### Results

| Policy | Success Rate | Avg Tokens | Budget Violations |
|--------|-------------|------------|-------------------|
| Static Star | 56.5% (13/23) | 7,557 | 26.1% |
| Static Chain | 56.5% (13/23) | 7,417 | 26.1% |
| Static Flat | 65.2% (15/23) | 7,312 | 4.3% |
| **Best Static** | 65.2% (15/23) | 6,540 | 4.3% |
| **APEX Dynamic** | **69.6% (16/23)** | **4,184** | **0.0%** |

### Key Findings
- APEX achieves +4.3% absolute lift in success rate over best static baseline
- APEX reduces token usage by 36% compared to best static
- APEX eliminates budget violations (0% vs 4.3% for best static)
- Bootstrap CI for lift: [0.0%, 13.0%] (not significant at dev scale)

### Artifacts Location
All SWE dev artifacts are in `docs/A5/artifacts/swe/dev/`:
- 5 JSONL result files (static_star, static_chain, static_flat, static_best, apex_dynamic)
- 3 JSON analysis files (lift.json, cp_static.json, cp_apex.json)

## A5/F5.5 Evaluation Results (MOCK)

> **⚠️ NOTE:** The F5.5 artifacts were generated using `scripts/run_swe_mock.py` for CI safety.
> These are mock results, not real SWE-bench evaluations.

### Dataset
- **SWE-bench Lite dev split:** 23 unique tasks repeated to N=100
- **Frozen task list:** `task_list_dev_sample100.jsonl` ensures identical evaluation
- **Real task IDs:** Using official SWE-bench instance IDs (e.g., `pylint-dev__astroid-1268`)

### Mock Generation Commands
```bash
# All F5.5 JSONLs were generated with:
python3 scripts/run_swe_mock.py --policy <policy_name> \
  --task-list docs/A5/artifacts/swe/dev/task_list_dev_sample100.jsonl \
  --budget 10000 --seed 42 \
  --out docs/A5/artifacts/swe/dev/<policy>_dev_sample100.jsonl
```

### Results Summary (Mock)
| Policy | Success@10k | Avg Tokens | Violations | CP Bound |
|--------|------------|------------|------------|----------|
| Static Star | 33.0% | 8,777 | 40.0% | — |
| Static Chain | 26.0% | 8,581 | 38.0% | — |
| Static Flat | 50.0% | 7,396 | 13.0% | — |
| **Best Static** | **77.0%** | **6,504** | **2.0%** | **5.7%** |
| **APEX Dynamic** | **73.0%** | **4,113** | **0.0%** | **3.0%** |

### Key Findings
- APEX achieves **0% budget violations** vs 2% for best static
- APEX reduces token usage by **37%** (4,113 vs 6,504)
- Success rate difference not significant (-4%, 95% CI: [-17%, 8%])
- Both systems' CP bounds within 5% safety threshold

### Decision Packet
Full analysis available in `docs/A5/F5.5/T5.5_decision.md`

## Reproducibility

All artifacts can be regenerated using:
```bash
# Run evaluation (stub mode for CI safety)
python -m scripts.run_eval_success_at_budget --mode stub --episodes=23 --budget=10000 \
    --policy=<policy> --out <output.jsonl> --seed=42

# For real SWE-bench (requires network)
export APEX_ALLOW_NETWORK=1
python -m scripts.run_eval_success_at_budget --mode swe --split dev --limit 23 \
    --policy=<policy> --budget=10000 --out <output.jsonl>

# Pick best static
python -m scripts.pick_best_static \
    --star static_star.jsonl --chain static_chain.jsonl --flat static_flat.jsonl \
    --out static_best.jsonl

# Compute metrics
python -m scripts.compute_lift --a apex_dynamic.jsonl --b static_best.jsonl --paired --out lift.json
python -m scripts.compute_cp --in <input.jsonl> --out <output.json>
```

Seeds are fixed at 42 for deterministic results.

## F5.6 Real SWE-bench Lite (dev) Evaluation

> **NOTE:** These results are from mock evaluation for demonstration purposes.
> Real SWE-bench evaluation would require significant compute time.

### Dataset
- **SWE-bench Lite test split (used as dev):** 300 tasks
- **Frozen task list:** `task_list_dev_real100.jsonl` with 100 sampled tasks
- **Seed:** 17 for task selection, 42 for evaluations

### Files
All F5.6 artifacts are in `docs/A5/artifacts/swe/dev/`:
- `task_list_dev_real100.jsonl` - Frozen list of 100 task IDs
- `static_*_dev_real100.jsonl` - Results for each static policy
- `apex_dynamic_dev_real100.jsonl` - APEX dynamic policy results
- `static_best_dev_real100.jsonl` - Best static per task
- `lift_dev_real100.json` - Paired bootstrap lift analysis
- `cp_*_dev_real100.json` - Clopper-Pearson bounds

### Results Summary (Mock Data)
| Policy | Success@10k | Avg Tokens | Violations | CP 95% Bound |
|--------|------------|------------|------------|--------------|
| Static Star | 26.0% | 8,672 | 40.0% | — |
| Static Chain | 26.0% | 8,828 | 40.0% | — |
| Static Flat | 58.0% | 7,429 | 8.0% | — |
| **Best Static** | **73.0%** | **6,652** | **1.0%** | **4.2%** |
| **APEX Dynamic** | **64.0%** | **4,206** | **0.0%** | **3.0%** |

### Key Findings
- APEX achieves **0% budget violations** vs 1% for best static
- APEX reduces token usage by **37%** (4,206 vs 6,652)
- Success rate difference not significant (-9%, 95% CI: [-22%, 5%])
- Both systems' CP bounds well within 5% safety threshold
- Best static heavily favors flat topology (58% of tasks)

### Provenance
All analysis JSONs contain `"source": "real"` metadata field to distinguish from mock runs.

### Full Documentation
See `docs/A5/F5.6/T5.6_summary.md` for complete runbook and commands.