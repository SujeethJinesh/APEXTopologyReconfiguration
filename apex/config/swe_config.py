"""SWE-bench configuration module."""

from apex.config import defaults


def get_swe_config():
    """Get SWE-bench configuration.
    
    Returns:
        dict: Configuration for SWE evaluation
    """
    return {
        "llm_backend": defaults.LLM_BACKEND,
        "llm_model_id": defaults.LLM_MODEL_ID,
        "num_instances": defaults.LLM_NUM_INSTANCES,
        "gguf_model_path": defaults.GGUF_MODEL_PATH,
        "warmup_tokens": defaults.WARMUP_TOKENS,
        "timeout_s": defaults.LLM_TIMEOUT_S,
        "episode_timeout_s": defaults.EPISODE_TIMEOUT_S,
        "allow_network": defaults.ALLOW_NETWORK,
    }