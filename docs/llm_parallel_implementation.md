# Parallel LLM Instance Implementation

## Summary
Implemented true process-based isolation for parallel LLM instances to prevent context contamination between agents.

## Key Components

### 1. MultiInstanceLLMManager (`apex/llm/manager.py`)
- Creates N separate ProcessPoolExecutors, each with 1 worker
- Each worker process gets a unique backend instance
- Deterministic agent_id → instance_id mapping
- True process isolation prevents context leakage

### 2. PortableLLMClient (`apex/llm/client.py`)
- Maintains compatibility with existing LLMClient interface
- Token budget tracking with hard denials
- Deterministic instance selection based on agent_id hash
- Supports both stub mode (testing) and real backends

### 3. Smoke Test (`apex/llm/smoke.py`)
- Runs 5 parallel prompts to verify isolation
- Tests concurrent generation capability
- Validates token tracking and stats

### 4. Isolation Tests (`tests/test_llm_parallel_isolation.py`)
- Test no cross-contamination between parallel agents
- Test session isolation (different sessions don't share context)
- Test instance distribution across agents

## Architecture

```
PortableLLMClient
    ↓
MultiInstanceLLMManager
    ↓
N x ProcessPoolExecutor (1 worker each)
    ↓
N x Backend Instance (isolated processes)
```

## Key Invariants

1. **Process Isolation**: Each backend runs in its own process
2. **Deterministic Mapping**: `agent_id` maps to same instance consistently
3. **No Context Sharing**: Sessions are isolated within instances
4. **Budget Enforcement**: Hard token budget limits per episode

## Usage

```python
# Create client (auto-starts manager)
client = PortableLLMClient()

# Generate with specific agent
response = await client.complete(
    prompt="Your prompt",
    agent_id="Agent_1",  # Deterministically maps to instance
    session_id="session_123",
    max_tokens=100
)

# Token stats
stats = client.get_stats()
print(f"Tokens used: {stats['tokens_used']}/{stats['budget']}")
```

## Environment Variables

- `APEX_LLM_BACKEND`: Backend selection (llama_cpp_metal or hf_cuda)
- `APEX_NUM_LLM_INSTANCES`: Number of parallel instances (default 5)
- `APEX_LLM_STUB`: Set to 1 for stub mode (no real model)
- `APEX_GGUF_MODEL_PATH`: Path to GGUF model file
- `APEX_HF_MODEL_ID`: HuggingFace model identifier

## Testing

```bash
# Run isolation tests
APEX_LLM_STUB=1 python3 -m pytest tests/test_llm_parallel_isolation.py -xvs

# Run smoke test
APEX_LLM_STUB=1 python3 -m apex.llm.smoke

# With real model
export APEX_GGUF_MODEL_PATH=/path/to/model.gguf
python3 -m apex.llm.smoke
```

## Performance

- Warmup time: ~0.2s (stub mode)
- Concurrent generation: N agents can generate simultaneously
- Process overhead: Minimal with spawn context
- Memory: N × model_size (each instance loads model)