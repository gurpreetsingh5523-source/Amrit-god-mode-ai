"""YAML config loader with environment variable override."""
import os, yaml
from pathlib import Path
from logger import setup_logger

logger = setup_logger("Config")

class ConfigLoader:
    _instance = None
    _config: dict = {}

    def __new__(cls, config_path="config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load(config_path)
        return cls._instance

    def _load(self, path):
        p = Path(path)
        if p.exists():
            with open(p) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            logger.warning(f"Config '{path}' not found — using defaults")
            self._config = {}
        self._apply_env()
        logger.info(f"Config loaded ({len(self._config)} sections)")

    def _apply_env(self):
        for env, (section, key) in {
            "OPENAI_API_KEY":    ("llm", "openai_api_key"),
            "ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
            "GROQ_API_KEY":      ("llm", "groq_api_key"),
            "GEMINI_API_KEY":    ("llm", "gemini_api_key"),
        }.items():
            v = os.getenv(env)
            if v:
                self._config.setdefault(section, {})[key] = v

    def get(self, *keys, default=None):
        node = self._config
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k)
        return node if node is not None else default

    def all(self):
        return dict(self._config)
