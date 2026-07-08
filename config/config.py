"""
config.py — CFG shim for DualBrain v3 compatibility.
Bridges DualBrain's CFG expectations to Amrit God Mode's config_loader.
"""
from pathlib import Path


class _CFG:
    """Drop-in replacement for DualBrain's CFG object."""
    memory_dir    = Path("workspace/dual_brain")
    sandbox_dir   = Path("workspace/dual_brain/sandbox")
    vault_dir     = Path("workspace/dual_brain/vault")
    dreams_dir    = Path("workspace/dual_brain/dreams")
    self_db       = Path("workspace/dual_brain/self_graph.db")
    dream_batch   = 5
    sandbox_timeout = 10
    ollama_url    = "http://localhost:11434"
    default_model = "qwen3.5:9b"
    fast_model    = "qwen3.5:9b"
    code_model    = "qwen3.5:9b"

    def __init__(self):
        # Try to read from Amrit's config_loader
        try:
            from config_loader import ConfigLoader
            cfg = ConfigLoader()
            model = cfg.get("llm", {}).get("model", self.default_model)
            if model:
                self.default_model = model
                self.fast_model = model
                self.code_model = model
        except Exception:
            pass
        # Ensure dirs exist
        for d in [self.memory_dir, self.sandbox_dir, self.vault_dir]:
            d.mkdir(parents=True, exist_ok=True)


CFG = _CFG()
