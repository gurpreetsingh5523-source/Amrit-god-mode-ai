"""Dataset Builder — builds coding / math / Punjabi JSONL training datasets.

Generates ChatML-formatted JSONL files that can be fine-tuned with
mlx_lm or the Hugging Face Trainer.

Subjects supported:
    coding  — Python coding tasks (functions, debugging, refactoring)
    math    — Arithmetic / algebra word problems with step-by-step solutions
    punjabi — Punjabi instruction-following prompts

Usage:
    from dataset_builder import DatasetBuilder
    db = DatasetBuilder()
    path = db.build("coding", n=200)   # returns path to .jsonl
    path = db.build("math",   n=150)
    path = db.build("punjabi",n=100)
"""
from __future__ import annotations

import json
import random
import textwrap
from pathlib import Path
from logger import setup_logger

logger = setup_logger("DatasetBuilder")

OUTPUT_DIR = Path("datasets/finetune")

SYSTEM_PROMPTS = {
    "coding":  "You are AMRIT, an expert Python coder. Answer with clean, working code.",
    "math":    "You are AMRIT, a math tutor. Solve step-by-step and show your work.",
    "punjabi": (
        "ਤੂੰ AMRIT ਹੈਂ — ਪੰਜਾਬੀ AI assistant। "
        "ਪੰਜਾਬੀ ਵਿੱਚ ਪੁੱਛੋ ਤਾਂ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।"
    ),
}

# ── Coding templates ──────────────────────────────────────────────
_CODING_QA: list[tuple[str, str]] = [
    ("Write a Python function to reverse a string.",
     "def reverse_string(s: str) -> str:\n    return s[::-1]"),
    ("Write a Python function to check if a number is prime.",
     textwrap.dedent("""\
     def is_prime(n: int) -> bool:
         if n < 2:
             return False
         for i in range(2, int(n**0.5) + 1):
             if n % i == 0:
                 return False
         return True""")),
    ("Write a Python function to flatten a nested list.",
     textwrap.dedent("""\
     def flatten(lst):
         result = []
         for item in lst:
             if isinstance(item, list):
                 result.extend(flatten(item))
             else:
                 result.append(item)
         return result""")),
    ("Write a Python function to count word frequency in a string.",
     textwrap.dedent("""\
     from collections import Counter
     def word_freq(text: str) -> dict:
         return dict(Counter(text.lower().split()))""")),
    ("Write a Python function to find the longest common prefix in a list of strings.",
     textwrap.dedent("""\
     def longest_common_prefix(strs: list[str]) -> str:
         if not strs:
             return ''
         prefix = strs[0]
         for s in strs[1:]:
             while not s.startswith(prefix):
                 prefix = prefix[:-1]
                 if not prefix:
                     return ''
         return prefix""")),
    ("Write a Python async function that fetches a URL and returns the text.",
     textwrap.dedent("""\
     import aiohttp
     async def fetch(url: str) -> str:
         async with aiohttp.ClientSession() as session:
             async with session.get(url) as resp:
                 return await resp.text()""")),
    ("Write a Python function to merge two sorted lists.",
     textwrap.dedent("""\
     def merge_sorted(a: list, b: list) -> list:
         result, i, j = [], 0, 0
         while i < len(a) and j < len(b):
             if a[i] <= b[j]:
                 result.append(a[i]); i += 1
             else:
                 result.append(b[j]); j += 1
         return result + a[i:] + b[j:]""")),
    ("Explain what a Python decorator is and give a simple example.",
     textwrap.dedent("""\
     A decorator is a function that wraps another function to add behaviour.
     Example:
     def log(fn):
         def wrapper(*args, **kwargs):
             print(f'Calling {fn.__name__}')
             return fn(*args, **kwargs)
         return wrapper

     @log
     def greet(name):
         return f'Hello, {name}'""")),
    ("Fix this Python code that raises a KeyError:\n  d = {'a': 1}\n  print(d['b'])",
     "Use .get() with a default:\n  print(d.get('b', 'not found'))"),
    ("Write a Python class for a stack using a list.",
     textwrap.dedent("""\
     class Stack:
         def __init__(self):
             self._data = []
         def push(self, val):
             self._data.append(val)
         def pop(self):
             if not self._data:
                 raise IndexError('Stack is empty')
             return self._data.pop()
         def peek(self):
             return self._data[-1] if self._data else None
         def is_empty(self):
             return len(self._data) == 0""")),
]

# ── Math templates ────────────────────────────────────────────────
_MATH_QA: list[tuple[str, str]] = [
    ("What is 17 × 23?",
     "Step 1: 17 × 20 = 340\nStep 2: 17 × 3  = 51\nStep 3: 340 + 51 = **391**"),
    ("A train travels 360 km in 4 hours. What is its average speed?",
     "Speed = Distance ÷ Time = 360 ÷ 4 = **90 km/h**"),
    ("Solve: 3x + 7 = 22",
     "3x = 22 − 7 = 15\nx = 15 ÷ 3 = **5**"),
    ("What is the area of a circle with radius 7 cm? (use π ≈ 3.14)",
     "Area = π × r² = 3.14 × 49 = **153.86 cm²**"),
    ("If a bag costs ₹450 after a 10% discount, what was the original price?",
     "Original = 450 ÷ 0.9 = **₹500**"),
    ("Find the LCM of 12 and 18.",
     "12 = 2²×3, 18 = 2×3²\nLCM = 2²×3² = 4×9 = **36**"),
    ("What is 25% of 320?",
     "25% = 1/4 → 320 ÷ 4 = **80**"),
    ("A rectangle has length 15 m and width 8 m. What is its perimeter?",
     "Perimeter = 2 × (15 + 8) = 2 × 23 = **46 m**"),
    ("Solve: 2x² − 8 = 0",
     "2x² = 8 → x² = 4 → x = **±2**"),
    ("What is the sum of interior angles of a hexagon?",
     "(n−2)×180 = (6−2)×180 = 4×180 = **720°**"),
]

# ── Punjabi templates ────────────────────────────────────────────
_PUNJABI_QA: list[tuple[str, str]] = [
    ("ਪਾਈਥਨ ਵਿੱਚ list comprehension ਕੀ ਹੈ?",
     "List comprehension ਇੱਕ ਛੋਟਾ ਤਰੀਕਾ ਹੈ list ਬਣਾਉਣ ਦਾ।\n"
     "ਉਦਾਹਰਣ: `[x*2 for x in range(5)]` → `[0, 2, 4, 6, 8]`"),
    ("ਭਾਰਤ ਦੀ ਰਾਜਧਾਨੀ ਕਿਹੜੀ ਹੈ?",
     "ਭਾਰਤ ਦੀ ਰਾਜਧਾਨੀ **ਨਵੀਂ ਦਿੱਲੀ** ਹੈ।"),
    ("ਮਸ਼ੀਨ ਲਰਨਿੰਗ ਅਤੇ ਡੀਪ ਲਰਨਿੰਗ ਵਿੱਚ ਕੀ ਫ਼ਰਕ ਹੈ?",
     "ML ਵਿੱਚ features manually ਦੇਣੇ ਪੈਂਦੇ ਹਨ, "
     "Deep Learning ਖੁਦ features ਸਿੱਖਦੀ ਹੈ neural networks ਰਾਹੀਂ।"),
    ("ਪਾਈਥਨ ਵਿੱਚ exception handling ਕਿਵੇਂ ਕਰਦੇ ਹਨ?",
     "try/except ਵਰਤਦੇ ਹਾਂ:\n```python\ntry:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print('ਗਲਤੀ: ਜ਼ੀਰੋ ਨਾਲ ਭਾਗ ਨਹੀਂ ਹੋ ਸਕਦਾ')\n```"),
    ("Git commit ਅਤੇ Git push ਵਿੱਚ ਕੀ ਫ਼ਰਕ ਹੈ?",
     "commit ਤਬਦੀਲੀਆਂ local ਸੇਵ ਕਰਦਾ ਹੈ, "
     "push ਉਹ ਤਬਦੀਲੀਆਂ GitHub ਵਰਗੇ remote ਤੇ ਭੇਜਦਾ ਹੈ।"),
]


CHATML = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{user}<|im_end|>\n"
    "<|im_start|>assistant\n{assistant}<|im_end|>"
)


class DatasetBuilder:
    """Build fine-tuning JSONL for coding, math or Punjabi subjects."""

    def build(self, subject: str = "coding", n: int = 100) -> str:
        """
        Generate `n` training examples for the given subject.
        Returns path to the saved JSONL file.
        """
        subject = subject.lower()
        if subject not in SYSTEM_PROMPTS:
            raise ValueError(f"Unknown subject '{subject}'. Choose from: {list(SYSTEM_PROMPTS)}")

        pool = {"coding": _CODING_QA, "math": _MATH_QA, "punjabi": _PUNJABI_QA}[subject]
        system = SYSTEM_PROMPTS[subject]

        examples = []
        for i in range(n):
            q, a = pool[i % len(pool)]
            # Add slight variation for repeated examples
            if i >= len(pool):
                q = q + " (variant)"
            examples.append({
                "text": CHATML.format(system=system, user=q, assistant=a)
            })
        random.shuffle(examples)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"{subject}_train.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for ex in examples:
                json.dump(ex, f, ensure_ascii=False)
                f.write("\n")

        logger.info(f"✅ Dataset built: {out_path} ({len(examples)} examples)")
        return str(out_path)

    def build_all(self, n_each: int = 100) -> dict[str, str]:
        """Build datasets for all subjects. Returns {subject: path}."""
        return {s: self.build(s, n_each) for s in SYSTEM_PROMPTS}

    def stats(self, path: str) -> dict:
        """Return quick stats about a JSONL dataset."""
        p = Path(path)
        if not p.exists():
            return {"error": f"{path} not found"}
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        total_chars = sum(len(ln) for ln in lines)
        return {
            "file": str(p),
            "examples": len(lines),
            "avg_chars": round(total_chars / max(len(lines), 1)),
            "total_chars": total_chars,
        }
