#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_evaluator.py — Multi-Signal Fitness Function

DeepMind "From AGI to ASI" (5.3, recursive self-improvement) ਦਾ ਮੁੱਖ ਨੁਕਤਾ:
  ਪੇਪਰ ਜਿਸ Socratic-learning framework 'ਤੇ ਖੜ੍ਹਾ ਹੈ (Schaul 2024), ਉਹ
  ਕਹਿੰਦਾ ਹੈ ਕਿ self-improvement loop ਤਾਂ ਹੀ ਕੰਮ ਕਰਦਾ ਹੈ ਜੇ feedback
  (a) informative ਅਤੇ (b) aligned ਹੋਵੇ। ਮਤਲਬ — ਖ਼ਰਾਬ fitness signal
  loop ਨੂੰ ਗ਼ਲਤ ਦਿਸ਼ਾ ਵੱਲ ਲੈ ਜਾਂਦਾ ਹੈ।

ਇਸ ਲਈ ਪੁਰਾਣਾ "fitness = 1 - len(output)/1000" ਪੂਰੀ ਤਰ੍ਹਾਂ ਹਟਾਇਆ।

ਨਵੇਂ weights (ਤੁਹਾਡੀ ਸਿਫ਼ਾਰਸ਼ ਮੁਤਾਬਕ):
    45%  Hidden Tests   — ਅਸਲ correctness (ਸਭ ਤੋਂ ਵੱਡਾ signal)
    20%  Property Tests — invariants ਹਰ input 'ਤੇ ਸਹੀ?
    15%  Syntax         — AST parse ਹੁੰਦਾ ਹੈ?
    10%  Sandbox        — ਚੱਲਿਆ ਬਿਨਾਂ crash?
     5%  Security       — static scan pass?
     5%  Diversity      — echo-chamber ਤੋਂ ਬਚਾਅ

ਮਹੱਤਵਪੂਰਨ ਡਿਜ਼ਾਈਨ ਫੈਸਲਾ:
  ਜੇ hidden/property tests ਉਪਲਬਧ ਨਹੀਂ, ਉਹਨਾਂ ਦਾ weight 0 ਰਹਿੰਦਾ ਹੈ
  (renormalize ਨਹੀਂ ਕਰਦੇ)। ਮਤਲਬ tests ਤੋਂ ਬਿਨਾਂ ਕੋਡ ਵੱਧ ਤੋਂ ਵੱਧ ~0.35
  ਤੱਕ ਹੀ ਪਹੁੰਚ ਸਕਦਾ ਹੈ। ਇਹ ਜਾਣ-ਬੁੱਝ ਕੇ ਹੈ — ਪੇਪਰ ਦਾ ਨੁਕਤਾ ਕਿ
  "ਬਿਨਾਂ ਚੰਗੇ feedback ਦੇ ਅਸੀਂ correctness 'ਤੇ ਭਰੋਸਾ ਨਹੀਂ ਕਰ ਸਕਦੇ।"
"""

import ast
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict


WEIGHTS = {
    "hidden":    0.45,
    "property":  0.20,
    "syntax":    0.15,
    "sandbox":   0.10,
    "security":  0.05,
    "diversity": 0.05,
}


@dataclass
class EvalResult:
    """ਇੱਕ candidate ਦਾ ਪੂਰਾ evaluation ਨਤੀਜਾ"""
    total: float
    breakdown: Dict[str, float] = field(default_factory=dict)
    complete: bool = False          # ਕੀ hidden+property ਦੋਵੇਂ ਉਪਲਬਧ ਸਨ?
    note: str = ""

    def render(self) -> str:
        parts = [f"{k}={v:.3f}" for k, v in self.breakdown.items()]
        tag = "" if self.complete else "  ⚠️ (no tests — capped)"
        return f"fitness={self.total:.3f} [{', '.join(parts)}]{tag}"


def evaluate(
    code: str,
    *,
    security_ok: bool,
    sandbox_ran: bool,
    hidden: Tuple[int, int] = (0, 0),
    prop: Tuple[int, int] = (0, 0),
    previous_code: Optional[str] = None,
) -> EvalResult:
    """
    ਇੱਕ code candidate ਦੀ ਬਹੁ-ਪੱਖੀ fitness ਮਾਪੋ।

    Parameters:
        code          : ਜਾਂਚਣ ਵਾਲਾ ਕੋਡ
        security_ok   : SecurityGuard ਪਾਸ ਹੋਇਆ?
        sandbox_ran   : sandbox ਵਿੱਚ bਿਨਾਂ crash ਚੱਲਿਆ?
        hidden        : (pass, total) hidden tests
        prop          : (pass, total) property tests
        previous_code : diversity ਲਈ ਪਿਛਲਾ ਕੋਡ

    Returns:
        EvalResult
    """
    # ── security fail = ਸਿੱਧਾ 0 (ਕੋਡ ਚਲਾਉਣਾ ਹੀ ਨਹੀਂ ਚਾਹੀਦਾ) ──
    if not security_ok:
        return EvalResult(0.0, {"security": 0.0}, False, "BLOCKED by SecurityGuard")

    # ── syntax: ਜੇ parse ਨਹੀਂ ਹੁੰਦਾ, ਸਭ ਬੇਕਾਰ ──
    try:
        ast.parse(code)
    except SyntaxError as e:
        return EvalResult(0.02, {"syntax": 0.0}, False, f"SyntaxError line {e.lineno}")

    bd: Dict[str, float] = {}
    bd["syntax"]   = WEIGHTS["syntax"]   * 1.0
    bd["sandbox"]  = WEIGHTS["sandbox"]  * (1.0 if sandbox_ran else 0.0)
    bd["security"] = WEIGHTS["security"] * 1.0   # ਇੱਥੇ ਪਹੁੰਚੇ = pass

    # ── Hidden tests (45%) ──
    hp, ht = hidden
    hid_avail = ht > 0
    bd["hidden"] = WEIGHTS["hidden"] * (hp / ht) if hid_avail else 0.0

    # ── Property tests (20%) ──
    pp, pt = prop
    prop_avail = pt > 0
    bd["property"] = WEIGHTS["property"] * (pp / pt) if prop_avail else 0.0

    # ── Diversity (5%) — echo-chamber ਤੋਂ ਬਚਾਅ ──
    if previous_code is None:
        diversity = 1.0
    else:
        a = set(previous_code.strip().split("\n"))
        b = set(code.strip().split("\n"))
        union = len(a | b)
        diversity = 1.0 - (len(a & b) / union if union else 1.0)
    bd["diversity"] = WEIGHTS["diversity"] * diversity

    total = round(sum(bd.values()), 3)
    complete = hid_avail and prop_avail
    note = "" if complete else "hidden/property tests missing → score capped"
    return EvalResult(total, bd, complete, note)


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("═" * 55)
    print("📊 multi_evaluator — Self Test")
    print("═" * 55)

    good = "def f(n):\n    return 1 if n < 2 else n * f(n-1)"

    cases = [
        ("perfect (all tests pass)",
         dict(security_ok=True, sandbox_ran=True, hidden=(4, 4), prop=(1, 1))),
        ("half hidden tests fail",
         dict(security_ok=True, sandbox_ran=True, hidden=(2, 4), prop=(1, 1))),
        ("no tests available (capped)",
         dict(security_ok=True, sandbox_ran=True, hidden=(0, 0), prop=(0, 0))),
        ("security blocked",
         dict(security_ok=False, sandbox_ran=False, hidden=(4, 4), prop=(1, 1))),
    ]

    prev = None
    for name, kw in cases:
        r = evaluate(good, previous_code=prev, **kw)
        print(f"\n📋 {name}")
        print(f"   {r.render()}")
        prev = good + "\n# variant"   # ਅਗਲੀ ਵਾਰ diversity ਦਿਖਾਉਣ ਲਈ

    # ── ordering assertion ──
    perfect = evaluate(good, security_ok=True, sandbox_ran=True, hidden=(4, 4), prop=(1, 1))
    half    = evaluate(good, security_ok=True, sandbox_ran=True, hidden=(2, 4), prop=(1, 1))
    capped  = evaluate(good, security_ok=True, sandbox_ran=True, hidden=(0, 0), prop=(0, 0))
    assert perfect.total > half.total > capped.total, "ordering broken!"
    print("\n✅ Ordering correct: perfect > half > capped")
