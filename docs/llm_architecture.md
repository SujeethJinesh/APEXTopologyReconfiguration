# APEX LLM Architecture

## Overview
The APEX framework uses a portable, process-isolated LLM architecture that provides true multi-instance concurrency with per-agent context separation. This replaces the previous Ollama-based single-server design.

## Architecture Components

### 1. Multi-Instance Manager (`apex/llm/manager.py`)
- **Process Pool**: Uses `ProcessPoolExecutor` with spawn context for true isolation
- **Instance Management**: Spawns N independent model processes (default: 5)
- **Warmup Protocol**: Runs warmup inference on all instances before readiness
- **Async Interface**: Full async/await support for concurrent requests

### 2. Backend Abstraction (`apex/llm/backends/base.py`)
- **Protocol Interface**: Defines standard LLMBackend protocol
- **Portable API**: Same interface works for both Mac and H100
- **Session Support**: Explicit session_id for context tracking
- **Timeout Handling**: Per-request timeout enforcement

### 3. Backend Implementations

#### llama.cpp Metal Backend (Mac Default)
- **Model Format**: GGUF quantized models (Q4_K_M recommended)
- **Acceleration**: Metal GPU offload (n_gpu_layers=-1)
- **Memory**: ~5GB per instance for 8B model
- **Context**: 4096 tokens default
- **Path**: `apex/llm/backends/llama_cpp_metal.py`

#### HuggingFace CUDA Backend (H100)
- **Quantization**: BitsAndBytes 4-bit (NF4)
- **Model**: Meta-Llama-3.1-8B-Instruct
- **Device Mapping**: Round-robin across GPUs
- **Memory**: ~4GB per instance with 4-bit
- **Path**: `apex/llm/backends/hf_cuda.py`

### 4. Client Adapter (`apex/llm/client.py`)
- **Compatibility Layer**: Maintains old LLMClient interface
- **Agent Mapping**: Deterministic agent→instance mapping
- **Budget Enforcement**: Hard deny without network I/O
- **Progress Integration**: Reports to progress tracker

## Configuration

### Environment Variables
```bash
# Backend selection
APEX_LLM_BACKEND=llama_cpp_metal  # or hf_cuda

# Model configuration
APEX_LLM_INSTANCES=5
APEX_LLM_CTX_TOKENS=4096
APEX_LLM_TIMEOUT_S=180
APEX_GGUF_MODEL_PATH=/models/Meta-Llama-3.1-8B-Instruct.Q4_K_M.gguf
APEX_LLM_MODEL_ID=meta-llama/Meta-Llama-3.1-8B-Instruct  # HF only

# Timeouts
APEX_EPISODE_TIMEOUT_S=1800      # 30 min base
APEX_PROGRESS_EXTEND_S=120       # 2 min extensions
APEX_EPISODE_TIMEOUT_MAX_S=3600  # 60 min max
```

### Agent Instance Mapping
```python
# Deterministic mapping by agent role
instance_id = abs(hash(agent_id)) % num_instances

# Standard roles → instances
Planner  → Instance 0
Coder    → Instance 1  
Runner   → Instance 2
Critic   → Instance 3
Summarizer → Instance 4
```

## Progress-Aware Timeouts

### Progress Events
- Test discovery/execution
- File writes/patches
- Token usage increases
- Topology switches
- LLM responses

### Timeout Extension Logic
```python
if progress_detected and near_deadline:
    extend_deadline(progress_extend_s)
    # Cap at episode_timeout_max_s
```

### Heartbeat Logging
- Every 20s: Log episode status
- Includes: tokens_used, last_progress, time_remaining
- Format: JSON for easy parsing

## Process Isolation Benefits

1. **True Concurrency**: Each instance runs in separate process
2. **Context Separation**: No shared memory between agents
3. **Resilience**: Crashed instance doesn't affect others
4. **Resource Control**: Per-process memory limits
5. **Clean Shutdown**: ProcessPoolExecutor handles cleanup

## Startup Sequence

```python
# 1. Create manager with backend factory
manager = MultiInstanceLLMManager(
    backend_factory=lambda i: LlamaCppMetalBackend(i, model_path),
    num_instances=5
)

# 2. Start all instances
await manager.start()  # Spawns processes

# 3. Warmup phase
# Automatically runs warmup("test") on each instance

# 4. Ready gate
assert manager.ready()  # All instances ready

# 5. Generate
result = await manager.generate(
    instance_id=0,
    session_id="ep1:planner",
    prompt="...",
    max_new_tokens=256
)
```

## Memory Requirements

### Mac (64GB RAM)
- 5 instances × 5GB = 25GB for models
- 5 instances × 4K context × 2 bytes = 40MB context
- Total: ~26GB LLM footprint

### H100 (80GB VRAM)
- 5 instances × 4GB = 20GB with 4-bit quant
- Plenty of headroom for larger contexts

## CI/Testing Support

### Stub Backend
```python
# Activated by APEX_LLM_STUB=1
class StubBackend:
    def generate(...):
        return mock_response_based_on_keywords(prompt)
```

### Mock Mode
- No model loading
- Instant responses
- Deterministic for testing
- Token counting preserved

## Migration from Ollama

### Removed
- All `aiohttp` calls to Ollama API
- Single-server bottleneck
- Shared context issues
- Complex async queuing

### Added
- Process-level isolation
- Multi-instance concurrency
- Explicit session management
- Progress-aware timeouts
- Portable backend abstraction

## Performance Characteristics

| Metric | Ollama (Old) | Portable (New) |
|--------|--------------|----------------|
| Instances | 1 | 5 |
| Concurrency | Queue-based | True parallel |
| Context Isolation | None | Per-process |
| Startup Time | ~5s | ~15s (warmup) |
| Memory Usage | ~5GB | ~26GB |
| Fault Tolerance | Single point | Instance-level |
| Timeout Control | Basic | Progress-aware |

## Future Enhancements

1. **Dynamic Scaling**: Add/remove instances based on load
2. **Model Variants**: Different models per role
3. **Distributed**: Multi-node instance pools
4. **Caching**: Shared KV cache for common prefixes
5. **Monitoring**: Prometheus metrics per instance