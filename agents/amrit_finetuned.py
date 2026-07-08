"""
amrit_finetuned.py — Amrit's OWN fine-tuned coding brain (MLX + LoRA adapter)
═══════════════════════════════════════════════════════════════════════════
Loads Qwen2.5-Coder-7B + the LoRA adapter Amrit trained on its verified data,
and exposes a simple complete(). Lazy-loaded (only when first used) so it never
bloats normal Amrit startup. Wired into llm_router as model "amrit-coder".

    from amrit_finetuned import complete
    print(complete("Write a function to reverse a linked list"))
"""
from pathlib import Path
from logger import setup_logger

logger = setup_logger("AmritFineTuned")

BASE_MODEL = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
# Prefer the best adapter we have (v3 → v2 → v1).
_ADAPTER_CANDIDATES = [
    "workspace/amrit_lora_adapter_v3",
    "workspace/amrit_lora_adapter_v2",
    "workspace/amrit_lora_adapter",
]

_loaded = None  # (model, tokenizer) cached after first load


def _adapter_path() -> str | None:
    for p in _ADAPTER_CANDIDATES:
        if (Path(p) / "adapters.safetensors").exists():
            return p
    return None


# The 7B 4-bit model needs ~6GB working memory; loading it with less free RAM
# triggers a hard Metal OOM that CRASHES the process (uncatchable). So we gate on
# free RAM and fall back to the cloud brain when memory is tight.
MIN_FREE_GB = 6.0


def _enough_ram() -> bool:
    try:
        import psutil
        return psutil.virtual_memory().available / 1e9 >= MIN_FREE_GB
    except Exception:
        return True


def is_available() -> bool:
    """True only if MLX + adapter exist AND there's enough free RAM to load safely."""
    try:
        import mlx_lm  # noqa
    except Exception:
        return False
    if _adapter_path() is None:
        return False
    if _loaded is None and not _enough_ram():
        logger.warning(f"fine-tuned model skipped: <{MIN_FREE_GB}GB RAM free → using cloud brain")
        return False
    return True


def _ensure_loaded():
    global _loaded
    if _loaded is None:
        from mlx_lm import load
        ap = _adapter_path()
        logger.info(f"🧠 loading Amrit fine-tuned model (adapter: {ap}) …")
        _loaded = load(BASE_MODEL, adapter_path=ap)
        logger.info("🧠 Amrit fine-tuned model ready")
    return _loaded


def complete(prompt: str, system: str = None, max_tokens: int = 400) -> str:
    """Generate with Amrit's own fine-tuned coder. Chat-formatted."""
    model, tok = _ensure_loaded()
    from mlx_lm import generate
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    try:
        text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    except Exception:
        text = prompt
    out = generate(model, tok, prompt=text, max_tokens=max_tokens, verbose=False)
    # strip any chat end-tokens
    return out.split("<|im_end|>")[0].strip()


if __name__ == "__main__":
    print("available:", is_available(), "| adapter:", _adapter_path())
    if is_available():
        print("─" * 50)
        print(complete("Write a Python function to check if a number is an Armstrong number.",
                       max_tokens=160))
