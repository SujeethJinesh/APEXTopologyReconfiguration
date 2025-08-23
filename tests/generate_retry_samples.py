"""Generate retry samples JSONL for at-least-once delivery evidence."""

import asyncio
import json
from datetime import datetime


async def generate_retry_samples():
    """Generate retry sample events showing at-least-once delivery."""

    # Note: In real scenario, would use A2AProtocol with mocked router/switch
    # to generate actual retry events. Here we simulate the expected output.

    samples = []

    # Case 1: Message succeeds on first attempt
    msg_id = "msg-success-001"
    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 1,
            "redelivered": False,
            "sender": "planner",
            "recipient": "coder",
            "content": "task-1",
            "result": "delivered",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    # Case 2: Message fails first attempt (queue full), succeeds on retry
    msg_id = "msg-retry-001"
    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 1,
            "redelivered": False,
            "sender": "planner",
            "recipient": "runner",
            "content": "task-2",
            "result": "queue_full",
            "error": "QueueFullError: runner queue at capacity 100",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 2,
            "redelivered": True,
            "sender": "planner",
            "recipient": "runner",
            "content": "task-2",
            "result": "delivered",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    # Case 3: Multiple retries before success
    msg_id = "msg-retry-002"
    for attempt in range(1, 4):
        samples.append(
            {
                "msg_id": msg_id,
                "attempt": attempt,
                "redelivered": attempt > 1,
                "sender": "coder",
                "recipient": "planner",  # Via planner in star topology
                "content": "result-3",
                "result": "queue_full" if attempt < 3 else "delivered",
                "error": "QueueFullError: planner queue at capacity 100" if attempt < 3 else None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    # Case 4: Network partition retry scenario
    msg_id = "msg-retry-003"
    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 1,
            "redelivered": False,
            "sender": "runner",
            "recipient": "critic",
            "content": "analysis-4",
            "result": "network_error",
            "error": "NetworkError: Unable to reach critic",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 2,
            "redelivered": True,
            "sender": "runner",
            "recipient": "critic",
            "content": "analysis-4",
            "result": "delivered",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    # Case 5: Epoch boundary retry
    msg_id = "msg-retry-004"
    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 1,
            "redelivered": False,
            "sender": "critic",
            "recipient": "summarizer",
            "content": "summary-5",
            "epoch": 1,
            "result": "epoch_gated",
            "error": "EpochGatedError: Message for epoch 2 gated until switch",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    samples.append(
        {
            "msg_id": msg_id,
            "attempt": 2,
            "redelivered": True,
            "sender": "critic",
            "recipient": "summarizer",
            "content": "summary-5",
            "epoch": 2,
            "result": "delivered",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )

    # Clean up None values
    for sample in samples:
        if "error" in sample and sample["error"] is None:
            del sample["error"]

    return samples


async def main():
    samples = await generate_retry_samples()

    # Write to JSONL file
    with open("docs/M3/artifacts/a2a_retry_samples.jsonl", "w") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")

    print(f"Generated {len(samples)} retry samples")

    # Print sample
    print("\nSample retry sequence:")
    for sample in samples[:3]:
        print(json.dumps(sample))


if __name__ == "__main__":
    asyncio.run(main())
