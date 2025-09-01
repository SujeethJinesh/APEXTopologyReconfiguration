"""Real topology switch implementation for dynamic switching."""

import time
from enum import Enum
from typing import Optional, Tuple

from .semantics import TopologySemantics


class TopologyType(Enum):
    """Topology types."""
    STAR = "star"
    CHAIN = "chain"
    FLAT = "flat"


class TopologySwitch:
    """Real topology switch for dynamic reconfiguration.
    
    This manages the actual topology transitions with proper
    state management and coordination.
    """
    
    def __init__(self, initial_topology: TopologyType = TopologyType.STAR):
        """Initialize topology switch.
        
        Args:
            initial_topology: Starting topology
        """
        self.current_topology = initial_topology
        self.current_epoch = 0
        self.last_switch_time = time.time()
        self.switch_cooldown = 0.1  # 100ms cooldown
        self.switch_history = []
        
        # Track switching state
        self.switching = False
        self.switch_start_time = None
        
    def active(self) -> Tuple[str, int]:
        """Get currently active topology and epoch.
        
        Returns:
            Tuple of (topology name, epoch number)
        """
        return self.current_topology.value, self.current_epoch
    
    def can_switch(self) -> bool:
        """Check if switching is allowed now.
        
        Returns:
            True if cooldown period has passed
        """
        if self.switching:
            return False
            
        elapsed = time.time() - self.last_switch_time
        return elapsed >= self.switch_cooldown
    
    def begin_switch(self, target_topology: TopologyType) -> bool:
        """Begin topology switch process.
        
        Args:
            target_topology: Target topology type
            
        Returns:
            True if switch initiated, False if not allowed
        """
        if not self.can_switch():
            return False
            
        if target_topology == self.current_topology:
            return False  # Already in target topology
            
        # Begin switch
        self.switching = True
        self.switch_start_time = time.time()
        
        # Record in history
        self.switch_history.append({
            "from": self.current_topology.value,
            "to": target_topology.value,
            "epoch": self.current_epoch,
            "timestamp": self.switch_start_time
        })
        
        return True
        
    def commit_switch(self, target_topology: TopologyType) -> int:
        """Commit the topology switch.
        
        Args:
            target_topology: Target topology to switch to
            
        Returns:
            New epoch number
        """
        if not self.switching:
            # Allow direct switch if not in switching state
            # (for simplified operation)
            self.begin_switch(target_topology)
            
        # Update topology and epoch
        self.current_topology = target_topology
        self.current_epoch += 1
        self.last_switch_time = time.time()
        
        # Clear switching state
        self.switching = False
        self.switch_start_time = None
        
        return self.current_epoch
        
    def abort_switch(self):
        """Abort an in-progress switch."""
        self.switching = False
        self.switch_start_time = None
        
    def get_switch_latency(self) -> Optional[float]:
        """Get latency of current switch in ms.
        
        Returns:
            Latency in milliseconds if switching, None otherwise
        """
        if not self.switching or not self.switch_start_time:
            return None
            
        return (time.time() - self.switch_start_time) * 1000
        
    def get_stats(self) -> dict:
        """Get switch statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            "current_topology": self.current_topology.value,
            "current_epoch": self.current_epoch,
            "total_switches": len(self.switch_history),
            "switching": self.switching,
            "can_switch": self.can_switch(),
            "switch_history": self.switch_history[-5:] if self.switch_history else []
        }