# A4 Artifacts

## Structure

- **Sample files (trimmed):** JSONL files in this directory contain up to 200 lines for review
- **Full files (compressed):** Complete artifacts stored in `raw/*.jsonl.gz`

## Files

| File | Sample Lines | Full Lines | Description |
|------|-------------|------------|-------------|
| controller_decisions.jsonl | 10 | 10 | Controller decision logs with features |
| controller_latency.jsonl | 200 | 10,000 | Decision latency measurements |
| rewards.jsonl | 25 | 25 | Per-step reward components |
| smoke_test_decisions.jsonl | 100 | 100 | Smoke test decision logs |
| smoke_test_rewards.jsonl | 99 | 99 | Smoke test reward logs |
| dwell_test_decisions.jsonl | 4 | 4 | Dwell constraint test |
| cooldown_test_decisions.jsonl | 5 | 5 | Cooldown constraint test |

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
Histogram bins for latency analysis:
- Buckets: [0-0.1ms, 0.1-0.5ms, 0.5-1ms, 1-5ms, 5-10ms, 10ms+]
- p95 recomputed: 0.1ms (9994/10000 decisions < 0.1ms)