"""SWE-specific configuration for evaluation."""

from apex.config.defaults import (
    APEX_LLM_BACKEND,
    LLM_NUM_INSTANCES,
    LLM_CTX_TOKENS,
    LLM_TIMEOUT_S,
)


def get_swe_config():
    """Get SWE-optimized configuration.
    
    Returns:
        dict: Configuration dictionary with SWE-specific settings
    """
    return {
        'backend': APEX_LLM_BACKEND,
        'num_instances': LLM_NUM_INSTANCES,
        'context_tokens': LLM_CTX_TOKENS,
        'timeout_s': LLM_TIMEOUT_S,
        'max_memory_per_instance_gb': 8.0,  # Conservative memory limit
    }