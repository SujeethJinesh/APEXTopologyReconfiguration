#!/usr/bin/env python3
"""Generate real task list from Hugging Face SWE-bench Lite dataset."""

from datasets import load_dataset
import random
import json

# Load official SWE-bench Lite dataset
print("Loading SWE-bench Lite dataset from Hugging Face...")
ds = load_dataset("SWE-bench/SWE-bench_Lite", split="dev")

print(f"Total tasks in dev split: {len(ds)}")

# Stable shuffle with seed 42
rng = random.Random(42)
indices = list(range(len(ds)))
rng.shuffle(indices)

# Select first 100 (but dev only has 23, so we'll repeat as needed)
sample_size = min(100, len(ds))
if sample_size < 100:
    print(f"Note: dev split only has {len(ds)} tasks, will create repetitions")
    
# Create task list
task_list = []

# First, add all unique tasks
for i in range(sample_size):
    row = ds[indices[i]]
    task_list.append({"task_id": row["instance_id"]})

# If we need more than available, add repetitions
if len(task_list) < 100:
    rep = 1
    while len(task_list) < 100:
        for i in range(len(ds)):
            if len(task_list) >= 100:
                break
            row = ds[indices[i]]
            task_list.append({"task_id": f"{row['instance_id']}__rep_{rep}"})
        rep += 1

# Write to file
output_path = "docs/A5/artifacts/swe/dev/task_list_dev_sample100.jsonl"
with open(output_path, "w") as f:
    for entry in task_list:
        json.dump(entry, f)
        f.write("\n")

print(f"\nGenerated task list with {len(task_list)} entries")
print(f"Output: {output_path}")
print("\nFirst 10 task IDs:")
for i, entry in enumerate(task_list[:10]):
    print(f"  {i+1}. {entry['task_id']}")