#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reflection_memory.py — Reflection Memory

DeepMind "From AGI to ASI" (5.3) ਅਤੇ ਸੰਬੰਧਿਤ meta-cognition ਖੋਜ
(MARS, Socratic Learning) ਦਾ ਨੁਕਤਾ: ਅਸਲ self-improvement ਤਾਂ ਹੀ
practical ਬਣਦੀ ਹੈ ਜਦੋਂ ਸਿਸਟਮ ਹਰ ਚੱਕਰ ਤੋਂ ਬਾਅਦ reflect ਕਰੇ —
"ਕੀ ਕੰਮ ਕੀਤਾ? ਕੀ ਫ਼ੇਲ੍ਹ ਹੋਇਆ? ਕਿਉਂ?" — ਅਤੇ ਉਹ ਸਿੱਖਿਆ ਅਗਲੀ ਵਾਰ ਵਰਤੇ।

failure_retrieval = ਸਿਰਫ਼ ਅਸਫ਼ਲਤਾਵਾਂ।
reflection_memory = ਸਫ਼ਲਤਾ ਦੇ patterns ਵੀ (ਕੀ ਤਰੀਕਾ ਕੰਮ ਆਇਆ)।
"""

import os
import json
import difflib
from datetime import datetime
from typing import List, Dict


def _similarity(a: str, b: str) -> float:
    a_l, b_l = a.lower(), b.lower()
    seq = difflib.SequenceMatcher(None, a_l, b_l).ratio()
    ta, tb = set(a_l.split()), set(b_l.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return 0.5 * seq + 0.5 * jac


class ReflectionMemory:
    """
    ਹਰ evolution ਤੋਂ ਬਾਅਦ ਦੀ ਸਿੱਖਿਆ ਸਟੋਰ ਕਰਦਾ ਹੈ।

    ਵਰਤੋਂ:
        rm = ReflectionMemory("reflection_memory.json")
        rm.add(task, what_worked=..., what_failed=..., why=..., fitness=0.96)
        guidance = rm.retrieve(new_task)   # ਅਗਲੇ prompt ਲਈ
    """

    def __init__(self, store_path: str = "reflection_memory.json"):
        self.store_path = store_path
        self.entries: List[Dict] = self._load()

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
                json.dump(self.entries, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, task: str, what_worked: str, what_failed: str,
            why: str, fitness: float):
        """ਇੱਕ reflection ਜੋੜੋ"""
        self.entries.append({
            "task": task,
            "what_worked": what_worked[:300],
            "what_failed": what_failed[:300],
            "why": why[:300],
            "fitness": round(fitness, 3),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save()

    def retrieve(self, task: str, k: int = 2, threshold: float = 0.15) -> str:
        """ਮਿਲਦੇ-ਜੁਲਦੇ task ਲਈ ਪੁਰਾਣੀ ਸਿੱਖਿਆ"""
        if not self.entries:
            return ""
        scored = [(e, _similarity(task, e["task"])) for e in self.entries]
        scored = [(e, s) for e, s in scored if s >= threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:k]
        if not top:
            return ""
        lines = ["💡 LESSONS from similar past tasks:"]
        for e, s in top:
            lines.append(f"  • Worked: {e['what_worked']}")
            if e["what_failed"]:
                lines.append(f"    Avoid : {e['what_failed']}")
        return "\n".join(lines) + "\n"

    def summary(self) -> Dict:
        """ਸਮੁੱਚਾ ਅੰਕੜਾ"""
        if not self.entries:
            return {"count": 0, "avg_fitness": 0.0}
        fits = [e["fitness"] for e in self.entries]
        return {"count": len(self.entries),
                "avg_fitness": round(sum(fits) / len(fits), 3)}


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "_rm_test.json")
    if os.path.exists(path):
        os.remove(path)

    rm = ReflectionMemory(path)
    rm.add("Write a factorial function",
           what_worked="iterative loop with input validation",
           what_failed="first version missed n==0 base case",
           why="forgot range(2, n+1) handles 0 and 1 automatically",
           fitness=0.96)

    print("═" * 55)
    print("🪞 ReflectionMemory — Self Test")
    print("═" * 55)
    g = rm.retrieve("Create a factorial calculator")
    print(g or "(no lessons)")
    print("Summary:", rm.summary())
    assert "iterative loop" in g, "should recall the working approach"
    assert rm.summary()["count"] == 1
    print("✅ Reflection stored and retrieved")
    os.remove(path)
