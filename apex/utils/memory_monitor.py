"""Memory monitoring utilities."""

import subprocess


def get_available_memory_gb():
    """Get available memory in GB.
    
    Returns:
        float: Available memory in GB
    """
    try:
        # Try macOS method first
        result = subprocess.run(
            ["vm_stat"], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse vm_stat output
            for line in result.stdout.split('\n'):
                if 'Pages free' in line:
                    pages_free = int(line.split(':')[1].strip().replace('.', ''))
                    # Page size is typically 4096 bytes
                    free_gb = (pages_free * 4096) / (1024 ** 3)
                    return free_gb
    except:
        pass
    
    # Fallback: assume 8GB available
    return 8.0


def check_memory_for_llm(num_instances=1, gb_per_instance=4.0):
    """Check if there's enough memory for LLM instances.
    
    Args:
        num_instances: Number of LLM instances
        gb_per_instance: GB required per instance
        
    Returns:
        tuple: (has_enough_memory, available_gb, required_gb)
    """
    available_gb = get_available_memory_gb()
    required_gb = num_instances * gb_per_instance
    has_enough = available_gb >= required_gb
    
    return has_enough, available_gb, required_gb


def log_memory_status(logger=None):
    """Log current memory status.
    
    Args:
        logger: Logger instance (uses print if None)
    """
    available_gb = get_available_memory_gb()
    
    msg = f"Available memory: {available_gb:.1f}GB"
    
    if logger:
        logger.info(msg)
    else:
        print(msg)