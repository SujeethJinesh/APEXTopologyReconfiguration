"""MVP defaults (subset used by tests; fuller set comes in later milestones)"""

import os
import platform

# ===== Runtime Configuration =====
QUIESCE_DEADLINE_MS = 50
DWELL_MIN_STEPS = 2
COOLDOWN_STEPS = 2
EPISODE_TOKEN_BUDGET = 10_000
QUEUE_CAP_PER_AGENT = 10_000
MESSAGE_TTL_S = 60
MAX_ATTEMPTS = 5

# ===== LLM Configuration =====
# Backend selection: "llama_cpp_metal" (Mac) or "hf_cuda" (H100)
# Auto-detect platform if not specified

if os.getenv("APEX_LLM_BACKEND"):
    APEX_LLM_BACKEND = os.getenv("APEX_LLM_BACKEND")
else:
    # Auto-detect based on platform
    if platform.system() == "Darwin":
        APEX_LLM_BACKEND = "llama_cpp_metal"
    else:
        # Check for CUDA availability
        try:
            import torch

            if torch.cuda.is_available():
                APEX_LLM_BACKEND = "hf_cuda"
            else:
                APEX_LLM_BACKEND = "llama_cpp_metal"  # Fallback
        except ImportError:
            APEX_LLM_BACKEND = "llama_cpp_metal"  # Fallback

LLM_BACKEND = APEX_LLM_BACKEND  # Alias for compatibility

# Number of parallel model instances (one per process) - guardrailed
# Default to 3 on Mac to avoid swap storms with 64GB RAM
DEFAULT_LLM_NUM_INSTANCES = 3 if platform.system() == "Darwin" else 5
APEX_NUM_LLM_INSTANCES = min(
    10, max(1, int(os.getenv("APEX_NUM_LLM_INSTANCES", str(DEFAULT_LLM_NUM_INSTANCES))))
)
LLM_NUM_INSTANCES = APEX_NUM_LLM_INSTANCES  # Alias

# Context window size in tokens - guardrailed
APEX_LLM_CTX_TOKENS = min(8192, max(512, int(os.getenv("APEX_LLM_CTX_TOKENS", "4096"))))
LLM_CTX_TOKENS = APEX_LLM_CTX_TOKENS  # Alias

# Per-request timeout in seconds - guardrailed
APEX_LLM_TIMEOUT_S = min(600, max(30, int(os.getenv("APEX_LLM_TIMEOUT_S", "180"))))
LLM_TIMEOUT_S = APEX_LLM_TIMEOUT_S  # Alias

# Model identifiers
APEX_HF_MODEL_ID = os.getenv(
    "APEX_HF_MODEL_ID", "meta-llama/Meta-Llama-3.1-8B-Instruct"
)  # For HF backend
LLM_MODEL_ID = APEX_HF_MODEL_ID  # Alias

# GGUF model path for llama.cpp backend
APEX_GGUF_MODEL_PATH = os.getenv("APEX_GGUF_MODEL_PATH", "")
GGUF_MODEL_PATH = APEX_GGUF_MODEL_PATH  # Alias

# Stub mode for testing (no real model)
LLM_STUB_MODE = os.getenv("APEX_LLM_STUB", "0") == "1"

# ===== Episode Configuration =====
# Episode timeout in seconds (default 30 minutes) - guardrailed
APEX_EPISODE_TIMEOUT_S = min(7200, max(300, int(os.getenv("APEX_EPISODE_TIMEOUT_S", "1800"))))
EPISODE_TIMEOUT_S = APEX_EPISODE_TIMEOUT_S  # Alias

# Progress extension in seconds (extend timeout when progress detected) - guardrailed
APEX_PROGRESS_EXTENSION_S = min(600, max(30, int(os.getenv("APEX_PROGRESS_EXTENSION_S", "120"))))
PROGRESS_EXTEND_S = APEX_PROGRESS_EXTENSION_S  # Alias

# Maximum episode timeout after extensions - guardrailed
APEX_EPISODE_TIMEOUT_MAX_S = min(
    10800, max(600, int(os.getenv("APEX_EPISODE_TIMEOUT_MAX_S", "3600")))
)
EPISODE_TIMEOUT_MAX_S = APEX_EPISODE_TIMEOUT_MAX_S  # Alias

# Progress heartbeat interval in seconds
HEARTBEAT_INTERVAL_S = int(os.getenv("APEX_HEARTBEAT_INTERVAL_S", "20"))
