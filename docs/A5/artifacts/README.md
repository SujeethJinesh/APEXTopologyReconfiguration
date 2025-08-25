# A5 Evaluation Artifacts

This directory contains machine-verifiable artifacts from the Success@Budget evaluation harness.

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

## Reproducibility

All artifacts can be regenerated using:
```bash
# Run evaluation
python -m scripts.run_eval_success_at_budget --episodes=12 --budget=10000 --policy=<policy> --out <output.jsonl> --seed=42

# Compute metrics
python -m scripts.compute_lift --a apex_dynamic.jsonl --b static_best.jsonl --out lift.json
python -m scripts.compute_cp --in <input.jsonl> --out <output.json>
```

Seeds are fixed at 42 for deterministic results.