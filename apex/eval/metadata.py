"""Episode metadata helpers."""

import platform
import os
from typing import Dict, Any


def get_episode_metadata() -> Dict[str, Any]:
    """Get metadata for episode artifacts."""
    from apex.config import defaults
    
    # Determine backend type
    backend = defaults.LLM_BACKEND
    
    # Determine device/platform
    if platform.system() == "Darwin":
        device = "mps"  # Metal Performance Shaders
    elif backend == "hf_cuda":
        device = "cuda"
    else:
        device = "cpu"
    
    # Get model info
    if backend == "llama_cpp_metal":
        model = os.path.basename(defaults.GGUF_MODEL_PATH or "Q4_K_M")
    else:
        model = defaults.LLM_MODEL_ID
    
    return {
        "__meta__": {
            "llm_backend": backend,
            "instances": defaults.LLM_NUM_INSTANCES,
            "model": model,
            "platform": device,
            "context_tokens": defaults.LLM_CTX_TOKENS,
            "episode_budget": defaults.EPISODE_TOKEN_BUDGET
        }
    }