"""Memory monitoring utilities for LLM instances."""

import os
import subprocess


def check_memory_for_llm(num_instances, gb_per_instance):
    """Check if system has enough memory for LLM instances.
    
    Args:
        num_instances: Number of LLM instances to start
        gb_per_instance: Memory requirement per instance in GB
        
    Returns:
        tuple: (can_start: bool, message: str)
    """
    try:
        # Try to get memory info using system commands
        if hasattr(os, 'sysconf') and hasattr(os, 'sysconf_names') and 'SC_PAGESIZE' in os.sysconf_names and 'SC_PHYS_PAGES' in os.sysconf_names:
            # Unix-like systems
            pagesize = os.sysconf('SC_PAGESIZE')
            pages = os.sysconf('SC_PHYS_PAGES')
            total_bytes = pagesize * pages
            total_gb = total_bytes / (1024**3)
            # Assume 50% available as rough estimate
            available_gb = total_gb * 0.5
        else:
            # Fallback: assume reasonable memory is available
            total_gb = 16.0  # Conservative estimate
            available_gb = 8.0  # Conservative available
        
        required_gb = num_instances * gb_per_instance
        
        # Check if we have enough available memory with 20% buffer
        buffer_factor = 1.2
        needed_gb = required_gb * buffer_factor
        
        can_start = available_gb >= needed_gb
        
        if can_start:
            message = (
                "Memory check passed: {:.1f}GB available "
                "for {} instances ({:.1f}GB needed)".format(
                    available_gb, num_instances, required_gb)
            )
        else:
            message = (
                "Memory check failed: {:.1f}GB available, "
                "{:.1f}GB needed for {} instances "
                "({}GB each + 20% buffer)".format(
                    available_gb, needed_gb, num_instances, gb_per_instance)
            )
        
        return can_start, message
        
    except Exception as e:
        return False, "Memory check error: {}".format(e)


def log_memory_status(prefix=""):
    """Log current memory status.
    
    Args:
        prefix: String prefix for log message
    """
    try:
        # Try to get basic memory info
        if hasattr(os, 'sysconf') and hasattr(os, 'sysconf_names') and 'SC_PAGESIZE' in os.sysconf_names and 'SC_PHYS_PAGES' in os.sysconf_names:
            pagesize = os.sysconf('SC_PAGESIZE')
            pages = os.sysconf('SC_PHYS_PAGES')
            total_bytes = pagesize * pages
            total_gb = total_bytes / (1024**3)
            print("{}Memory: ~{:.1f}GB total".format(prefix, total_gb))
        else:
            print("{}Memory: status unavailable".format(prefix))
              
    except Exception as e:
        print("{}Memory status error: {}".format(prefix, e))