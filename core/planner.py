#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planner.py — Planner Agent (ਅਗੇ ਤੋਂ ਸੋਚਣ ਵਾਲਾ ਦਿਮਾਗ਼)

DeepMind "From AGI to ASI" (5.4, multi-agent coordination): collective
ਤਾਂ ਹੀ individual agents ਨਾਲੋਂ ਵੱਧ smart ਬਣਦਾ ਹੈ ਜਦੋਂ ਕੰਮ ਨੂੰ
ਸਹੀ ਢੰਗ ਨਾਲ decompose ਅਤੇ coordinate ਕੀਤਾ ਜਾਵੇ।

ਨਵਾਂ flow:  Khoj → [Planner] → Nirman → Verifier → Vivek
Planner ਪਹਿਲਾਂ ਸੋਚਦਾ ਹੈ: ਕਿਹੜੇ steps, ਕਿਹੜਾ entry-point function,
ਕਿਹੜੇ constraints — ਤਾਂ ਜੋ Nirman ਅੰਨ੍ਹੇਵਾਹ ਕੋਡ ਨਾ ਲਿਖੇ।
"""

import json
import re
from typing import Dict


def _extract_json(text: str) -> dict:
    """LLM ਦੇ ਜਵਾਬ ਵਿੱਚੋਂ JSON ਕੱਢੋ (```json fences ਅਤੇ ਵਾਧੂ text ਸਾਫ਼ ਕਰਕੇ)"""
    if not text:
        return {}
    # ```json ... ``` ਹਟਾਓ
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    # ਸਿੱਧਾ try
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # ਪਹਿਲਾ {...} block ਲੱਭੋ
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


class PlannerAgent:
    """
    ਇੱਕ LLM agent ਨੂੰ wrap ਕਰਦਾ ਹੈ ਜੋ task ਦਾ structured plan ਬਣਾਉਂਦਾ ਹੈ।

    agent : ਕੋਈ ਵੀ object ਜਿਸ ਵਿੱਚ .execute(prompt).output ਹੋਵੇ
            (ਤੁਹਾਡੇ AgentBuilder ਦੇ agents ਇਸੇ ਤਰ੍ਹਾਂ ਕੰਮ ਕਰਦੇ ਹਨ)
    """

    def __init__(self, agent):
        self.agent = agent

    def plan(self, task: str, research: str = "", reflections: str = "") -> Dict:
        """
        Task ਦਾ plan ਬਣਾਓ।

        Returns dict:
            {
              "entry_point": "function_name",
              "steps": [...],
              "constraints": [...]
            }
        ਜੇ parse ਫ਼ੇਲ੍ਹ ਹੋਵੇ ਤਾਂ ਸੁਰੱਖਿਅਤ default ਵਾਪਸ ਕਰਦਾ ਹੈ।
        """
        prompt = (
            "You are a software planning specialist. Produce a concise plan.\n"
            "Respond ONLY with valid JSON (no prose, no markdown) in this shape:\n"
            '{"entry_point": "main_function_name", '
            '"steps": ["step 1", "step 2"], '
            '"constraints": ["constraint 1"]}\n\n'
            + (f"Research notes:\n{research}\n\n" if research else "")
            + (f"{reflections}\n" if reflections else "")
            + f"Task: {task}"
        )

        try:
            raw = self.agent.execute(prompt).output
        except Exception as e:
            return {"entry_point": "solution", "steps": [],
                    "constraints": [], "_error": str(e)}

        data = _extract_json(raw)

        # ── safe defaults ──
        return {
            "entry_point": data.get("entry_point") or "solution",
            "steps":       data.get("steps") or [],
            "constraints": data.get("constraints") or [],
        }


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    class _Resp:
        def __init__(self, o): self.output = o

    class _MockAgent:
        def execute(self, prompt):
            return _Resp('```json\n{"entry_point": "factorial", '
                         '"steps": ["validate input", "iterative multiply"], '
                         '"constraints": ["raise ValueError on negative"]}\n```')

    print("═" * 55)
    print("🗺️  PlannerAgent — Self Test")
    print("═" * 55)
    p = PlannerAgent(_MockAgent())
    plan = p.plan("Write a factorial function")
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    assert plan["entry_point"] == "factorial"
    assert len(plan["steps"]) == 2
    print("✅ Plan parsed correctly (handles ```json fences)")
