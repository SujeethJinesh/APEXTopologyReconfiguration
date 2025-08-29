"""llama.cpp backend with Metal acceleration for Mac."""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class LlamaCppMetalBackend:
    """llama.cpp backend using Metal acceleration on Mac.

    This backend uses GGUF quantized models for efficient inference
    on Apple Silicon with Metal GPU acceleration.
    """

    def __init__(
        self,
        instance_id: int,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        n_threads: int = 0,
        seed: int = 42,
        cache_dir: Optional[str] = None,
    ):
        """Initialize the backend.

        Args:
            instance_id: Instance identifier
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 for all)
            n_threads: Number of CPU threads (0 for auto)
            seed: Random seed for reproducibility
            cache_dir: Optional cache directory for this instance
        """
        self.instance_id = instance_id
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.seed = seed
        self._llm = None

        # Set up per-process cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path.home() / ".cache" / "apex" / "llm" / f"worker_{instance_id}"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Set environment for this process's cache
        os.environ["LLAMA_CACHE"] = str(self.cache_dir)

    def start(self) -> None:
        """Load the model."""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. " "Install with: pip install llama-cpp-python"
            )

        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,  # Metal offload all layers
            n_threads=self.n_threads or None,
            seed=self.seed,
            vocab_only=False,
            verbose=False,
        )

    def ready(self) -> bool:
        """Check if model is loaded."""
        return self._llm is not None

    def warmup(self, text: str = "Hello") -> None:
        """Run warmup inference."""
        if self._llm:
            _ = self._llm(text, max_tokens=8)

    def stop(self) -> None:
        """Unload the model."""
        self._llm = None

    def estimate_tokens(self, prompt: str, max_new_tokens: int) -> int:
        """Estimate total tokens using the actual tokenizer.

        Args:
            prompt: Input prompt text
            max_new_tokens: Maximum new tokens to generate

        Returns:
            Estimated total tokens (input + output)
        """
        if not self._llm:
            # Fallback to heuristic if model not loaded
            return (len(prompt) // 4) + max_new_tokens

        try:
            # Use actual tokenizer for accurate count
            tokens = self._llm.tokenize(prompt.encode("utf-8"), add_bos=True)
            return len(tokens) + max_new_tokens
        except Exception:
            # Fallback to heuristic on error
            return (len(prompt) // 4) + max_new_tokens

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
            session_id: Session identifier (for tracking, not used by stateless model)
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            stop: Optional stop sequences
            timeout_s: Timeout in seconds (handled by manager)

        Returns:
            Generation result dictionary
        """
        if not self._llm:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "error",
                "error": "Model not loaded",
            }

        try:
            # Estimate prompt tokens and clamp max_new_tokens to context window
            prompt_tokens_est = max(0, len(prompt) // 4)  # rough estimate
            room = self.n_ctx - prompt_tokens_est - 64  # leave 64 token buffer
            max_new_clamped = max(1, min(max_new_tokens, room))

            if max_new_clamped < max_new_tokens:
                print(
                    f"[Instance {self.instance_id}] Clamped max_tokens "
                    f"from {max_new_tokens} to {max_new_clamped} (context limit)"
                )

            t0 = time.time()
            out = self._llm(
                prompt,
                max_tokens=max_new_clamped,
                temperature=temperature,
                top_p=top_p,
                stop=stop or [],
                echo=False,
            )

            # Extract results
            text = out["choices"][0]["text"]
            tokens_in = len(out.get("prompt_token_ids", []))
            tokens_out = len(out["choices"][0].get("token_ids", []))
            finish_reason = out["choices"][0].get("finish_reason", "length")

            elapsed = time.time() - t0

            return {
                "text": text,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "finish_reason": finish_reason,
                "elapsed_s": elapsed,
                "session_id": session_id,
            }

        except Exception as e:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "error",
                "error": str(e),
            }
