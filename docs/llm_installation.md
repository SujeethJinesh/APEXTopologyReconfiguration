# LLM Backend Installation Guide

## Mac (Apple Silicon) Setup

### Prerequisites
- Apple Silicon Mac (M1/M2/M3) with 64GB RAM
- Python 3.11+
- Xcode Command Line Tools

### Installation

1. **Install llama-cpp-python with Metal support:**
```bash
# Ensure Metal acceleration is enabled
CMAKE_ARGS="-DLLAMA_METAL=on" pip install --upgrade --no-cache-dir llama-cpp-python==0.2.90
```

2. **Download GGUF model:**
```bash
# Recommended: Llama 3.1 8B Instruct Q4_K_M (4.92 GB)
wget https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf

# Set environment variable
export APEX_GGUF_MODEL_PATH=/path/to/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
```

3. **Configure instances:**
```bash
# Default: 3 instances on Mac (recommended for 64GB)
export APEX_NUM_LLM_INSTANCES=3  # Reduce to 2 if seeing swap usage
```

### Memory Requirements

| Model Size | Quant | Per Instance | 3 Instances | Notes |
|------------|-------|--------------|-------------|-------|
| 8B | Q4_K_M | ~5-6 GB | ~15-18 GB | Recommended |
| 8B | Q5_K_M | ~6-7 GB | ~18-21 GB | Better quality |
| 8B | Q8_0 | ~8-9 GB | ~24-27 GB | May swap |

**Note:** If you see swap usage or slowdowns, reduce `APEX_NUM_LLM_INSTANCES` to 2.

## H100 (CUDA) Setup

### Prerequisites
- NVIDIA H100 or similar GPU
- CUDA 11.8+
- Python 3.11+

### Installation

1. **Install PyTorch with CUDA:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

2. **Install transformers and bitsandbytes:**
```bash
pip install transformers accelerate bitsandbytes
```

3. **Set HuggingFace token (if using private models):**
```bash
export HF_TOKEN=your_token_here
```

4. **Configure model:**
```bash
# Default model
export APEX_HF_MODEL_ID=meta-llama/Meta-Llama-3.1-8B-Instruct

# Force HF backend
export APEX_LLM_BACKEND=hf_cuda

# Number of instances (per GPU or fractional)
export APEX_NUM_LLM_INSTANCES=5
```

### Memory Requirements

| Model Size | Precision | Per Instance | Notes |
|------------|-----------|--------------|-------|
| 8B | 4-bit (nf4) | ~6-8 GB | Recommended |
| 8B | fp16 | ~16 GB | Higher quality |
| 70B | 4-bit | ~40 GB | Multi-GPU needed |

## Environment Variables

| Variable | Description | Mac Default | H100 Default |
|----------|-------------|-------------|--------------|
| `APEX_LLM_BACKEND` | Backend selection | `llama_cpp_metal` | `hf_cuda` |
| `APEX_NUM_LLM_INSTANCES` | Parallel instances | 3 | 5 |
| `APEX_GGUF_MODEL_PATH` | Path to GGUF model | Required | N/A |
| `APEX_HF_MODEL_ID` | HuggingFace model ID | N/A | Required |
| `APEX_LLM_CTX_TOKENS` | Context window size | 4096 | 4096 |
| `APEX_LLM_TIMEOUT_S` | Per-request timeout | 180 | 180 |
| `APEX_LLM_STUB` | Use mock backend | 0 | 0 |
| `APEX_ALLOW_LLM` | Enable real LLM | 0 | 0 |

## Verification

### Quick smoke test:
```bash
# Stub mode (no model needed)
APEX_LLM_STUB=1 python -m apex.llm.smoke

# Real model
export APEX_GGUF_MODEL_PATH=/path/to/model.gguf
APEX_ALLOW_LLM=1 python -m apex.llm.smoke
```

### Test isolation:
```bash
APEX_LLM_STUB=1 python -m pytest tests/test_llm_parallel_isolation.py -v
```

## Troubleshooting

### Mac Issues

**"Metal not available"**
- Ensure CMAKE_ARGS="-DLLAMA_METAL=on" was used during installation
- Verify with: `python -c "from llama_cpp import Llama; print(Llama._llama_cpp._lib_path)"`

**Swap/slowdown**
- Reduce instances: `export APEX_NUM_LLM_INSTANCES=2`
- Use smaller quantization (Q4_K_M instead of Q5_K_M)
- Close other applications

**Model load fails**
- Check file path: `ls -la $APEX_GGUF_MODEL_PATH`
- Ensure sufficient free RAM: `vm_stat | grep free`

### H100 Issues

**CUDA out of memory**
- Reduce instances or use 4-bit quantization
- Check GPU memory: `nvidia-smi`

**Slow generation**
- Ensure using GPU: Check logs for "cuda" device
- Verify 4-bit is enabled: Should see "Loading in 4-bit"

## Performance Tips

1. **Mac**: Keep instances at 3 or below for 64GB RAM
2. **H100**: Can run 5+ instances with 4-bit quantization
3. **Context**: Start with 4096 tokens, increase if stable
4. **Timeouts**: 180s is usually sufficient for most tasks
5. **Cache**: Per-process caches prevent contention

## Additional Resources

- [llama.cpp documentation](https://github.com/ggerganov/llama.cpp)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)
- [BitsAndBytes quantization](https://github.com/TimDettmers/bitsandbytes)