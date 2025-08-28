"""MVP defaults (subset used by tests; fuller set comes in later milestones)"""

import os

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
LLM_BACKEND = os.getenv("APEX_LLM_BACKEND", "llama_cpp_metal")

# Number of parallel model instances (one per process)
LLM_NUM_INSTANCES = int(os.getenv("APEX_LLM_INSTANCES", "5"))

# Context window size in tokens
LLM_CTX_TOKENS = int(os.getenv("APEX_LLM_CTX_TOKENS", "4096"))

# Per-request timeout in seconds
LLM_TIMEOUT_S = int(os.getenv("APEX_LLM_TIMEOUT_S", "180"))

# Model identifiers
LLM_MODEL_ID = os.getenv(
    "APEX_LLM_MODEL_ID", "meta-llama/Meta-Llama-3.1-8B-Instruct"
)  # For HF backend

# GGUF model path for llama.cpp backend
GGUF_MODEL_PATH = os.getenv(
    "APEX_GGUF_MODEL_PATH",
    "/models/Meta-Llama-3.1-8B-Instruct.Q4_K_M.gguf",
)

# Stub mode for testing (no real model)
LLM_STUB_MODE = os.getenv("APEX_LLM_STUB", "0") == "1"

# ===== Episode Configuration =====
# Episode timeout in seconds (default 30 minutes)
EPISODE_TIMEOUT_S = int(os.getenv("APEX_EPISODE_TIMEOUT_S", "1800"))

# Progress extension in seconds (extend timeout when progress detected)
PROGRESS_EXTEND_S = int(os.getenv("APEX_PROGRESS_EXTEND_S", "120"))

# Maximum episode timeout after extensions
EPISODE_TIMEOUT_MAX_S = int(os.getenv("APEX_EPISODE_TIMEOUT_MAX_S", "3600"))

# Progress heartbeat interval in seconds
HEARTBEAT_INTERVAL_S = int(os.getenv("APEX_HEARTBEAT_INTERVAL_S", "20"))
