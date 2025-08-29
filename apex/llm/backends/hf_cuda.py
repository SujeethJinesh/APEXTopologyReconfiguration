"""Hugging Face backend with CUDA and 4-bit quantization for H100."""

import time
from typing import Any, Dict, List, Optional


class HFCudaBitsBackend:
    """HuggingFace Transformers backend with BitsAndBytes 4-bit quantization.

    This backend is designed for H100 GPUs with CUDA support.
    Uses 4-bit quantization for memory efficiency.
    """

    def __init__(
        self,
        instance_id: int,
        model_id: str,
        load_in_4bit: bool = True,
    ):
        """Initialize the backend.

        Args:
            instance_id: Instance identifier
            model_id: HuggingFace model ID
            load_in_4bit: Whether to use 4-bit quantization
        """
        self.instance_id = instance_id
        self.model_id = model_id
        self.load_in_4bit = load_in_4bit
        self.model = None
        self.tok = None
        self.device = None

    def start(self) -> None:
        """Load the model with quantization."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError:
            raise ImportError(
                "Missing dependencies for HF CUDA backend. Install with:\n"
                "pip install torch transformers accelerate bitsandbytes"
            )

        # Determine device
        if torch.cuda.is_available():
            self.device = f"cuda:{self.instance_id % torch.cuda.device_count()}"
        else:
            self.device = "cpu"

        # Quantization config for 4-bit
        qconf = None
        if self.load_in_4bit and self.device.startswith("cuda"):
            qconf = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )

        # Load model and tokenizer
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            device_map={"": self.device},
            torch_dtype=torch.float16,
            quantization_config=qconf,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )

        self.tok = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
        )

        # Set padding token if not set
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token

    def ready(self) -> bool:
        """Check if model is loaded."""
        return self.model is not None and self.tok is not None

    def warmup(self, text: str = "Hello") -> None:
        """Run warmup inference."""
        if self.ready():
            _ = self.generate(
                session_id="warmup",
                prompt=text,
                max_new_tokens=8,
            )

    def stop(self) -> None:
        """Unload the model."""
        self.model = None
        self.tok = None

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
            session_id: Session identifier
            prompt: Input prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            stop: Optional stop sequences (not directly supported)
            timeout_s: Timeout in seconds (handled by manager)

        Returns:
            Generation result dictionary
        """
        if not self.ready():
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "error",
                "error": "Model not loaded",
            }

        try:
            import torch

            t0 = time.time()

            # Tokenize input
            inputs = self.tok(prompt, return_tensors="pt").to(self.device)
            input_len = inputs["input_ids"].shape[1]

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=top_p,
                    eos_token_id=self.tok.eos_token_id,
                    pad_token_id=self.tok.eos_token_id,
                )

            # Extract generated text (exclude input)
            gen = outputs[0][input_len:]
            text = self.tok.decode(gen, skip_special_tokens=True)

            # Apply stop sequences if provided
            if stop:
                for stop_seq in stop:
                    if stop_seq in text:
                        text = text[: text.index(stop_seq)]
                        break

            elapsed = time.time() - t0

            return {
                "text": text,
                "tokens_in": int(inputs["input_ids"].numel()),
                "tokens_out": int(gen.numel()),
                "finish_reason": "length",  # Could be improved with proper detection
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
