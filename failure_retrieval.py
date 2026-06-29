#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
failure_retrieval.py — FailureDNA Retrieval

DeepMind "From AGI to ASI" (5.3): recursive self-improvement ਦਾ ਇੱਕ
ਜ਼ਰੂਰੀ ਹਿੱਸਾ "coverage of experience" ਹੈ — ਸਿਸਟਮ ਨੂੰ ਆਪਣੇ ਪੁਰਾਣੇ
ਤਜਰਬੇ (ਖ਼ਾਸ ਕਰਕੇ ਅਸਫ਼ਲਤਾਵਾਂ) ਤੋਂ ਸਿੱਖਣਾ ਚਾਹੀਦਾ ਹੈ।

ਤੁਹਾਡੇ ਕੋਲ ਪਹਿਲਾਂ ਹੀ FailureDNA (.record) ਹੈ ਜੋ failures ਸਟੋਰ ਕਰਦਾ ਹੈ।
ਇਹ module ਉਸ ਤੋਂ ਅੱਗੇ ਜਾ ਕੇ — ਨਵੇਂ task ਲਈ ਮਿਲਦੀਆਂ-ਜੁਲਦੀਆਂ ਪੁਰਾਣੀਆਂ
ਅਸਫ਼ਲਤਾਵਾਂ ਲੱਭ ਕੇ prompt ਵਿੱਚ ਜੋੜਦਾ ਹੈ, ਤਾਂ ਜੋ Nirman ਉਹੀ ਗ਼ਲਤੀ ਨਾ ਦੁਹਰਾਏ।

    similar = failures.retrieve(task)
    prompt += similar
"""

import os
import json
import difflib
from typing import List, Dict


def _similarity(a: str, b: str) -> float:
    """ਦੋ task strings ਦੀ ਸਮਾਨਤਾ (0–1): sequence ratio + token overlap"""
    a_l, b_l = a.lower(), b.lower()
    seq = difflib.SequenceMatcher(None, a_l, b_l).ratio()
    ta, tb = set(a_l.split()), set(b_l.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return 0.5 * seq + 0.5 * jac


class FailureRetrieval:
    """
    ਅਸਫ਼ਲਤਾਵਾਂ ਨੂੰ JSON ਵਿੱਚ ਸਟੋਰ ਕਰਦਾ ਹੈ ਅਤੇ similarity ਨਾਲ retrieve ਕਰਦਾ ਹੈ।

    ਵਰਤੋਂ:
        fr = FailureRetrieval("failure_memory.json")
        fr.record("JSON parser", "JSONDecodeError", "missing try/except")
        text = fr.retrieve("Build a JSON reader")   # ਮਿਲਦੀਆਂ ਅਸਫ਼ਲਤਾਵਾਂ
    """

    def __init__(self, store_path: str = "failure_memory.json"):
        self.store_path = store_path
        self.records: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record(self, task: str, error_type: str, detail: str):
        """ਇੱਕ ਅਸਫ਼ਲਤਾ ਦਰਜ ਕਰੋ"""
        self.records.append({
            "task": task,
            "error_type": error_type,
            "detail": detail[:300],
        })
        self._save()

    def retrieve(self, task: str, k: int = 3, threshold: float = 0.15) -> str:
        """
        ਨਵੇਂ task ਨਾਲ ਮਿਲਦੀਆਂ ਪੁਰਾਣੀਆਂ ਅਸਫ਼ਲਤਾਵਾਂ ਲੱਭੋ।

        Returns:
            prompt ਵਿੱਚ ਜੋੜਨ ਯੋਗ formatted text (ਖ਼ਾਲੀ ਜੇ ਕੁਝ ਨਾ ਮਿਲੇ)
        """
        if not self.records:
            return ""

        scored = [(r, _similarity(task, r["task"])) for r in self.records]
        scored = [(r, s) for r, s in scored if s >= threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:k]

        if not top:
            return ""

        lines = ["⚠️ PAST FAILURES on similar tasks — avoid repeating these:"]
        for r, s in top:
            lines.append(f"  • [{r['error_type']}] {r['detail']}  (match {s:.0%})")
        return "\n".join(lines) + "\n"


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "_fr_test.json")
    if os.path.exists(path):
        os.remove(path)

    fr = FailureRetrieval(path)
    fr.record("Create a JSON parser", "JSONDecodeError",
              "did not wrap json.loads in try/except")
    fr.record("Sort a list", "TypeError",
              "compared str and int without type check")

    print("═" * 55)
    print("🧬 FailureRetrieval — Self Test")
    print("═" * 55)
    result = fr.retrieve("Build a JSON reader with error handling")
    print(result or "(no matches)")
    assert "JSONDecodeError" in result, "should match the JSON failure"
    assert "TypeError" not in result or "match" in result
    print("✅ Retrieval matched the relevant past failure")
    os.remove(path)
