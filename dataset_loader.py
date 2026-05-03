"""Dataset Loader — loads JSONL fine-tuning datasets for training/evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from logger import setup_logger

logger = setup_logger("DatasetLoader")


class DatasetLoader:
    """Load ChatML JSONL datasets for fine-tuning."""

    def load(self, path: str) -> list[dict]:
        """Load all examples from a JSONL file. Returns list of dicts."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset not found: {path}")
        examples = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    examples.append(json.loads(line))
        logger.info(f"Loaded {len(examples)} examples from {p.name}")
        return examples

    def load_split(self, path: str, train_ratio: float = 0.9) -> tuple[list, list]:
        """Split dataset into train / validation sets."""
        import random
        examples = self.load(path)
        random.shuffle(examples)
        split = int(len(examples) * train_ratio)
        return examples[:split], examples[split:]

    def save(self, examples: list[dict], path: str) -> str:
        """Save examples to JSONL file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            for ex in examples:
                json.dump(ex, f, ensure_ascii=False)
                f.write("\n")
        logger.info(f"Saved {len(examples)} examples → {path}")
        return str(p)
