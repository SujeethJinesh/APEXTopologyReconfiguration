"""Base protocol for LLM backends."""

from typing import Any, Dict, List, Optional, Protocol


class LLMBackend(Protocol):
    """Protocol for LLM backend implementations.
    
    All backends must implement this interface for portability.
    """
    
    def start(self) -> None:
        """Initialize the model and load weights."""
        ...
    
    def ready(self) -> bool:
        """Check if the backend is ready for inference."""
        ...
    
    def warmup(self, text: str = "Hello") -> None:
        """Run a warmup inference to prime the model."""
        ...
    
    def stop(self) -> None:
        """Clean shutdown of the backend."""
        ...
    
    def generate(
        self,
        *,
        session_id: str,
        prompt: str,
        max_new_tokens: int,
        temperature: float = 0.7,
        top_p: float = 0.95,
        stop: Optional[List[str]] = None,
        timeout_s: int = 120,
    ) -> Dict[str, Any]:
        """Generate text completion.
        
        Args:
            session_id: Unique session identifier for context
            prompt: Input prompt text
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            stop: Optional stop sequences
            timeout_s: Timeout in seconds
            
        Returns:
            Dictionary with:
                text: Generated text
                tokens_in: Input token count
                tokens_out: Output token count
                finish_reason: "length" | "stop" | "timeout" | "error"
        """
        ...