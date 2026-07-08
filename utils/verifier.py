#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verifier.py — Verifier Agent (hallucinated-bug ਰੋਕੂ)

ਪੁਰਾਣੀ ਸਮੱਸਿਆ: Vivek ਨੂੰ "3 issues ਲੱਭੋ" ਕਿਹਾ ਜਾਂਦਾ ਸੀ — ਇਸ ਲਈ ਉਹ
ਸਾਫ਼-ਸੁਥਰੇ ਕੋਡ ਵਿੱਚ ਵੀ ਨਕਲੀ (hallucinated) bugs ਘੜ ਲੈਂਦਾ ਸੀ। ਇਹ
ਪੇਪਰ ਦੇ "aligned feedback" ਸਿਧਾਂਤ ਦੇ ਉਲਟ ਹੈ — ਗ਼ਲਤ feedback loop
ਨੂੰ ਖ਼ਰਾਬ ਕਰਦਾ ਹੈ।

ਨਵਾਂ Verifier:
  • 0–3 issues ਹੀ (ਜ਼ਬਰਦਸਤੀ 3 ਨਹੀਂ)
  • NO_ISSUES_FOUND ਦੀ ਆਗਿਆ
  • ਹਰ issue ਦੀ "validity" ਜਾਂਚ — ਕੀ ਇਹ ਅਸਲ ਕੋਡ ਵਿੱਚ ਮੌਜੂਦ ਚੀਜ਼
    ਵੱਲ ਇਸ਼ਾਰਾ ਕਰਦਾ ਹੈ? (grounding check — ਨਕਲੀ bug ਫੜਨ ਲਈ)
  • confidence score (0–1)
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


@dataclass
class VerifyResult:
    no_issues: bool
    issues: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    validity: float = 1.0          # ਕਿੰਨੇ issues ਅਸਲ ਕੋਡ ਨਾਲ grounded ਹਨ

    def render(self) -> str:
        if self.no_issues:
            return f"NO ISSUES (confidence {self.confidence:.2f})"
        return (f"{len(self.issues)} issue(s), "
                f"validity {self.validity:.2f}, confidence {self.confidence:.2f}")


class VerifierAgent:
    """
    agent : object ਜਿਸ ਵਿੱਚ .execute(prompt).output ਹੋਵੇ
    """

    def __init__(self, agent):
        self.agent = agent

    def verify(self, task: str, code: str, sandbox_output: str = "",
               plan: str = "") -> VerifyResult:
        """
        ਕੋਡ ਦੀ ਜਾਂਚ ਕਰੋ। 0–3 ਅਸਲ issues ਜਾਂ NO_ISSUES।
        """
        prompt = (
            "You are a strict but honest code verifier.\n"
            "Report ONLY real issues you can point to in the code. "
            "If the code is correct, report zero issues — do NOT invent problems.\n"
            "Report AT MOST 3 issues.\n\n"
            "Respond ONLY with valid JSON in this shape:\n"
            '{"no_issues": true/false, "confidence": 0.0-1.0, '
            '"issues": [{"location": "function or symbol name", '
            '"reason": "why it is wrong", "fix": "how to fix"}]}\n\n'
            + (f"Plan:\n{plan}\n\n" if plan else "")
            + f"TASK: {task}\n\n"
            + f"CODE:\n{code}\n\n"
            + f"SANDBOX OUTPUT (last 400 chars):\n{sandbox_output[-400:]}"
        )

        try:
            raw = self.agent.execute(prompt).output
        except Exception as e:
            # agent ਫ਼ੇਲ੍ਹ → ਸੁਰੱਖਿਅਤ ਪਾਸੇ: ਕੋਈ confident claim ਨਹੀਂ
            return VerifyResult(no_issues=False, issues=[], confidence=0.0, validity=0.0)

        data = _extract_json(raw)
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = []
        issues = issues[:3]   # ਵੱਧ ਤੋਂ ਵੱਧ 3

        no_issues = bool(data.get("no_issues", len(issues) == 0))
        if len(issues) == 0:
            no_issues = True

        # confidence clamp [0,1]
        try:
            confidence = float(data.get("confidence", 0.5))
        except Exception:
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        # ── validity / grounding check ──
        # ਹਰ issue ਦਾ "location" ਅਸਲ ਕੋਡ ਵਿੱਚ ਹੈ? ਨਕਲੀ bugs ਫੜਨ ਲਈ।
        validity = self._grounding(issues, code)

        return VerifyResult(no_issues=no_issues, issues=issues,
                            confidence=confidence, validity=validity)

    @staticmethod
    def _grounding(issues: List[Dict], code: str) -> float:
        """issues ਵਿੱਚੋਂ ਕਿੰਨੇ ਅਸਲ ਕੋਡ ਨਾਲ ਜੁੜੇ ਹਨ (0–1)"""
        if not issues:
            return 1.0
        code_l = code.lower()
        grounded = 0
        for it in issues:
            loc = str(it.get("location", "")).lower().strip()
            # location ਦਾ ਕੋਈ token ਕੋਡ ਵਿੱਚ ਮਿਲਦਾ ਹੈ?
            tokens = [t for t in re.split(r"[^a-zA-Z0-9_]+", loc) if len(t) > 2]
            if tokens and any(t in code_l for t in tokens):
                grounded += 1
        return round(grounded / len(issues), 3)

    def choose(self, task: str, candidates: List[str]) -> int:
        """
        Majority-voting tiebreak: ਜਦੋਂ ਦੋ candidates ਦੀ fitness ਨੇੜੇ ਹੋਵੇ,
        Verifier ਤੋਂ ਪੁੱਛੋ ਕਿਹੜਾ ਵੱਧ ਸਹੀ ਹੈ। (index ਵਾਪਸ)
        """
        if not candidates:
            return 0
        if len(candidates) == 1:
            return 0
        listing = "\n\n".join(
            f"--- CANDIDATE {i} ---\n{c}" for i, c in enumerate(candidates)
        )
        prompt = (
            "Pick the single most correct candidate for the task.\n"
            'Respond ONLY with JSON: {"best": <index>}\n\n'
            f"TASK: {task}\n\n{listing}"
        )
        try:
            raw = self.agent.execute(prompt).output
            data = _extract_json(raw)
            idx = int(data.get("best", 0))
            return idx if 0 <= idx < len(candidates) else 0
        except Exception:
            return 0


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    class _Resp:
        def __init__(self, o): self.output = o

    class _Grounded:
        def execute(self, p):
            return _Resp('{"no_issues": false, "confidence": 0.8, '
                         '"issues": [{"location": "factorial", '
                         '"reason": "no negative check", "fix": "raise ValueError"}]}')

    class _Hallucinated:
        def execute(self, p):
            return _Resp('{"no_issues": false, "confidence": 0.9, '
                         '"issues": [{"location": "quantum_handler", '
                         '"reason": "missing", "fix": "add it"}]}')

    code = "def factorial(n):\n    return 1 if n < 2 else n * factorial(n-1)"

    print("═" * 55)
    print("🔎 VerifierAgent — Self Test")
    print("═" * 55)

    g = VerifierAgent(_Grounded()).verify("factorial", code)
    print("Grounded issue   :", g.render())
    assert g.validity == 1.0, "real issue should be grounded"

    h = VerifierAgent(_Hallucinated()).verify("factorial", code)
    print("Hallucinated issue:", h.render())
    assert h.validity == 0.0, "fake issue ('quantum_handler') should score 0 validity"

    print("✅ Grounding check separates real bugs from hallucinated ones")
