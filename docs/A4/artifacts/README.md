# A4 Artifacts

## Structure

- **Sample files (trimmed):** JSONL files in this directory contain up to 200 lines for review
- **Full files (compressed):** Complete artifacts stored in `raw/*.jsonl.gz`

## Files

| File | Sample Lines | Full Lines | Description |
|------|-------------|------------|-------------|
| controller_decisions.jsonl | 10 | 10 | Controller decision logs with features |
| controller_latency.jsonl | 200 | 10,000 | Bandit decision latency measurements (milliseconds) |
| controller_tick_latency.jsonl | 200 | 10,000 | Full controller tick latency measurements (milliseconds) |
| rewards.jsonl | 25 | 25 | Per-step reward components |
| smoke_test_decisions.jsonl | 100 | 100 | Smoke test decision logs |
| smoke_test_rewards.jsonl | 99 | 99 | Smoke test reward logs |
| dwell_test_decisions.jsonl | 4 | 4 | Dwell constraint test |
| cooldown_test_decisions.jsonl | 5 | 5 | Cooldown constraint test |

**Units:** All latency measurements (`bandit_ms`, `tick_ms`) are in milliseconds.

## Validation

To validate JSONL format:
```bash
# Validate sample files
for f in *.jsonl; do
  python -c "import json; [json.loads(line) for line in open('$f')]"
  echo "$f: valid"
done

# Validate full files
for f in raw/*.jsonl.gz; do
  gunzip -c "$f" | python -c "import json, sys; [json.loads(line) for line in sys.stdin]"
  echo "$f: valid"
done
```

## Key Artifacts

### controller_latency_ms.bins.json
Histogram bins for **bandit** latency analysis:
- Buckets: [0-0.1ms, 0.1-0.5ms, 0.5-1ms, 1-5ms, 5-10ms, 10ms+]
- p95 recomputed: 0.1ms (9994/10000 decisions < 0.1ms)

### controller_tick_latency_ms.bins.json
Histogram bins for **full controller tick** latency analysis:
- Buckets: [0-0.1ms, 0.1-0.5ms, 0.5-1ms, 1-5ms, 5-10ms, 10ms+]
- p95 recomputed: 0.1ms (9958/10000 ticks < 0.1ms)

### Computing p95 from Histogram Bins
To recompute p95 from histogram bins for SLO verification:
1. Sum counts cumulatively from lowest to highest bucket
2. Find the first bucket where cumulative count ≥ 0.95 × total
3. The p95 is the **upper edge** of that bucket
4. Example: If 9500+ samples are in [0, 0.1ms), then p95 = 0.1ms