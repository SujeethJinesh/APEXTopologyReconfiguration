"""On-demand GGUF model fetcher for llama.cpp backend."""

import os
from pathlib import Path

from huggingface_hub import hf_hub_download


def ensure_gguf() -> str:
    """Ensure GGUF model is available, downloading if needed.

    Returns:
        Path to the GGUF model file
    """
    # Environment variables for configuration
    repo = os.environ.get("APEX_GGUF_REPO", "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF")
    fname = os.environ.get("APEX_GGUF_FILENAME", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf")
    target = os.environ.get("APEX_GGUF_MODEL_PATH", str(Path.home() / "models" / fname))

    target_p = Path(target)
    target_p.parent.mkdir(parents=True, exist_ok=True)

    # Check if already exists
    if target_p.exists() and target_p.stat().st_size > 1_000_000:  # > 1MB sanity check
        print(f"[APEX] Using existing GGUF model: {target_p}")
        return str(target_p)

    # Download from HuggingFace
    print(f"[APEX] Downloading {repo}/{fname} → {target}")
    print("[APEX] This may take a few minutes for the first download...")

    try:
        # Download to the target directory
        downloaded_path = hf_hub_download(
            repo_id=repo,
            filename=fname,
            local_dir=str(target_p.parent),
            local_dir_use_symlinks=False,
            resume_download=True,  # Resume if interrupted
        )

        # hf_hub_download may save into a repo subdir
        dl_p = Path(downloaded_path)

        # If downloaded to different location, move to target
        if dl_p.resolve() != target_p.resolve():
            if target_p.exists():
                target_p.unlink()  # Remove incomplete file if exists
            if dl_p.exists():  # Ensure source exists before rename
                dl_p.rename(target_p)

        print(f"[APEX] Download complete: {target_p} ({target_p.stat().st_size / 1e9:.2f} GB)")
        return str(target_p)

    except Exception as e:
        print(f"[APEX] Error downloading GGUF model: {e}")
        print("[APEX] Please manually download from:")
        print(f"  https://huggingface.co/{repo}/resolve/main/{fname}")
        print(f"  and save to: {target}")
        raise
