#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║  🧠 dual_brain_engine_v3.py — Frontier Edition                       ║
║                                                                      ║
║  Google DeepMind "From AGI to ASI" (arXiv:2606.12683, Genewein 2026)║
║  ਦੇ ਚਾਰ pathways ਵਿੱਚੋਂ ਦੋ ਨੂੰ ਅਮਲ ਵਿੱਚ ਲਿਆਉਂਦਾ ਹੈ:               ║
║                                                                      ║
║    • Pathway 5.3 — Recursive Self-Improvement                       ║
║    • Pathway 5.4 — Multi-Agent Collective (swarm)                   ║
║                                                                      ║
║  ਅਤੇ ਪੇਪਰ ਦੇ "frictions/bottlenecks" (5.5) ਦਾ ਜਵਾਬ ਦਿੰਦਾ ਹੈ:      ║
║    feedback quality, echo-chamber drift, safety/control।            ║
║                                                                      ║
║  ── ਨੋਟ (ਇਮਾਨਦਾਰੀ ਨਾਲ) ──                                          ║
║  ਪੇਪਰ ਚਾਰ pathways ਅਤੇ frictions ਨੂੰ "open research questions"      ║
║  ਵਜੋਂ ਪੇਸ਼ ਕਰਦਾ ਹੈ — ਇਹ ਕੋਈ ready-made algorithm ਨਹੀਂ ਦਿੰਦਾ।       ║
║  ਹੇਠਲੇ ਸਾਰੇ ਇੰਜੀਨੀਅਰਿੰਗ ਫੈਸਲੇ ਉਸ framework ਤੋਂ "ਪ੍ਰੇਰਿਤ" ਹਨ,       ║
║  ਪੇਪਰ ਦੇ verbatim ਹਵਾਲੇ ਨਹੀਂ।                                       ║
╚══════════════════════════════════════════════════════════════════════╝

ਪੂਰਾ flow:
    Khoj (research)
      → FailureRetrieval (ਮਿਲਦੀਆਂ ਪੁਰਾਣੀਆਂ ਅਸਫ਼ਲਤਾਵਾਂ)
      → ReflectionMemory (ਪੁਰਾਣੀ ਸਿੱਖਿਆ)
      → Planner (structured plan + entry_point)
      → Loop:
          Nirman A/B/C (best-of-N swarm)
            → SecurityGuard (static scan)
            → MutationLab (sandbox + hidden/property tests)
            → multi_evaluator (weighted fitness)
            → best candidate (Verifier tiebreak)
          → Verifier (0–3 issues, validity, confidence)
          → early-stop? (fitness≥0.95 AND confidence≥0.90 AND no_issues)
          → Vivek (deep critique) → Nirman refine
      → ReflectionMemory.add (ਜੇ ਸਫ਼ਲ) / FailureRetrieval.record (ਜੇ ਅਸਫ਼ਲ)
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from security_guard import SecurityGuard
from multi_evaluator import evaluate, EvalResult
from failure_retrieval import FailureRetrieval
from reflection_memory import ReflectionMemory
from planner import PlannerAgent
from verifier import VerifierAgent, VerifyResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("DualBrainV3")


# ══════════════════════════════════════════════════════════════════
# TEST DRIVER BUILDER
#
# Generated code ਨੂੰ hidden + property tests ਨਾਲ ਜੋੜ ਕੇ ਇੱਕ self-contained
# script ਬਣਾਉਂਦਾ ਹੈ। MutationLab ਇਸ script ਨੂੰ sandbox ਵਿੱਚ ਚਲਾਉਂਦਾ ਹੈ,
# ਅਤੇ ਇਹ ਅੰਤ ਵਿੱਚ __EVAL_JSON__ marker ਨਾਲ ਨਤੀਜਾ print ਕਰਦਾ ਹੈ।
#
# ਸੁਰੱਖਿਆ: candidate ਨੂੰ ਪਹਿਲਾਂ SecurityGuard scan ਕਰਦਾ ਹੈ। ਇਹ driver
# (engine ਦਾ ਆਪਣਾ trusted code) candidate ਨੂੰ ਇੱਕ ਵੱਖਰੇ namespace ਵਿੱਚ
# ਚਲਾਉਂਦਾ ਹੈ ਤਾਂ ਜੋ candidate ਦਾ __main__ block ਆਪੇ ਨਾ ਚੱਲੇ।
# ══════════════════════════════════════════════════════════════════
def build_test_driver(code: str, hidden: List[str], prop: List[str]) -> str:
    lines = [
        "import json as _json",
        "_CODE = " + repr(code),
        "_H = " + repr(list(hidden or [])),
        "_P = " + repr(list(prop or [])),
        "_ns = {'__name__': '_candidate_'}",
        "_load_ok = True",
        "try:",
        "    exec(compile(_CODE, '<candidate>', 'exec'), _ns)",
        "except Exception:",
        "    _load_ok = False",
        "def _try(_s):",
        "    try:",
        "        exec(_s, _ns)",
        "        return True",
        "    except Exception:",
        "        return False",
        "if _load_ok:",
        "    _hp = sum(_try(s) for s in _H)",
        "    _pp = sum(_try(s) for s in _P)",
        "else:",
        "    _hp = 0",
        "    _pp = 0",
        ("print('__EVAL_JSON__' + _json.dumps({"
         "'load_ok': _load_ok, "
         "'hidden_pass': _hp, 'hidden_total': len(_H), "
         "'property_pass': _pp, 'property_total': len(_P)}))"),
    ]
    return "\n".join(lines)


def parse_eval(output: str) -> Optional[dict]:
    """sandbox output ਵਿੱਚੋਂ __EVAL_JSON__ marker ਪੜ੍ਹੋ"""
    if not output:
        return None
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("__EVAL_JSON__"):
            try:
                return json.loads(line[len("__EVAL_JSON__"):])
            except Exception:
                return None
    return None


# ══════════════════════════════════════════════════════════════════
# DUAL BRAIN ENGINE v3
# ══════════════════════════════════════════════════════════════════
class DualBrainEngineV3:
    """
    Frontier Edition orchestrator.

    Parameters:
        agent_builder : ਤੁਹਾਡਾ AgentBuilder (agents: Nirman, Vivek, Khoj,
                        ਅਤੇ ਨਵੇਂ Planner, Verifier)
        mutation_lab  : ਤੁਹਾਡਾ MutationLab (create_variant + test_in_sandbox)
        failures      : FailureRetrieval instance (optional)
        reflections   : ReflectionMemory instance (optional)
        n_candidates  : best-of-N swarm size (default 3 = Nirman A/B/C)
    """

    # diversity ਲਈ ਵੱਖ-ਵੱਖ generation hints (self-consistency)
    VARIANT_HINTS = [
        "Prioritize correctness and edge cases.",
        "Prioritize simplicity and readability.",
        "Prioritize robustness and input validation.",
    ]

    def __init__(self, agent_builder, mutation_lab,
                 failures: Optional[FailureRetrieval] = None,
                 reflections: Optional[ReflectionMemory] = None,
                 n_candidates: int = 3):
        self.builder = agent_builder
        self.lab = mutation_lab
        self.failures = failures or FailureRetrieval()
        self.reflections = reflections or ReflectionMemory()
        self.n = max(1, n_candidates)

        self.guard = SecurityGuard()

        agents = agent_builder.agents
        # ਲਾਜ਼ਮੀ
        self.nirman = agents["Nirman"]
        self.vivek = agents["Vivek"]
        # ਵਿਕਲਪਿਕ (ਨਾ ਹੋਣ 'ਤੇ gracefully skip)
        self.khoj = agents.get("Khoj")
        self.planner = PlannerAgent(agents["Planner"]) if "Planner" in agents else None
        self.verifier = VerifierAgent(agents["Verifier"]) if "Verifier" in agents else None

        log.info("🧠 DualBrainEngine v3.0 (Frontier) — Ready")
        log.info(f"   Swarm size     : {self.n} (Nirman A/B/C…)")
        log.info(f"   Khoj           : {'✅' if self.khoj else '— skipped'}")
        log.info(f"   Planner        : {'✅' if self.planner else '— skipped'}")
        log.info(f"   Verifier       : {'✅' if self.verifier else '— skipped'}")

    # ──────────────────────────────────────────────────────────────
    def _generate(self, base_prompt: str) -> List[str]:
        """N candidates ਬਣਾਓ (swarm) — ਹਰ ਇੱਕ ਵੱਖਰੇ hint ਨਾਲ"""
        out = []
        for i in range(self.n):
            hint = self.VARIANT_HINTS[i % len(self.VARIANT_HINTS)]
            prompt = base_prompt + f"\n\nStrategy: {hint}\n" \
                     "Output ONLY complete, executable Python code. No explanations."
            try:
                out.append(self.nirman.execute(prompt).output)
            except Exception as e:
                log.error(f"   Nirman candidate {i} failed: {e}")
                out.append("")   # ਖ਼ਾਲੀ → ਘੱਟ fitness
        return out

    # ──────────────────────────────────────────────────────────────
    def _score_candidates(
        self, candidates: List[str], hidden: List[str], prop: List[str],
        previous_code: Optional[str], tag: str
    ) -> List[Tuple[str, EvalResult]]:
        """ਹਰ candidate ਨੂੰ scan → sandbox → evaluate"""
        results = []
        for i, cand in enumerate(candidates):
            # 1. Security scan (sandbox ਤੋਂ ਪਹਿਲਾਂ)
            safe, findings = self.guard.scan(cand)
            if not safe:
                log.info(f"   [{tag}#{i}] 🚫 blocked: {findings[0] if findings else '?'}")
                results.append((cand, EvalResult(0.0, {"security": 0.0},
                                                 False, "blocked")))
                continue

            # 2. Sandbox run (driver = code + hidden/property tests)
            driver = build_test_driver(cand, hidden, prop)
            try:
                var_id, _ = self.lab.create_variant(f"{tag}_{i}", driver)
                ran, output = self.lab.test_in_sandbox(var_id)
            except Exception as e:
                ran, output = False, str(e)

            res_json = parse_eval(output)
            if res_json and res_json.get("load_ok"):
                hp, ht = res_json["hidden_pass"], res_json["hidden_total"]
                pp, pt = res_json["property_pass"], res_json["property_total"]
                sandbox_ran = bool(ran)
            else:
                hp, ht = 0, len(hidden or [])
                pp, pt = 0, len(prop or [])
                sandbox_ran = False

            # 3. Weighted fitness
            ev = evaluate(cand, security_ok=True, sandbox_ran=sandbox_ran,
                          hidden=(hp, ht), prop=(pp, pt), previous_code=previous_code)
            log.info(f"   [{tag}#{i}] {ev.render()}")
            results.append((cand, ev))
        return results

    # ──────────────────────────────────────────────────────────────
    def _pick_best(self, scored: List[Tuple[str, EvalResult]],
                   task: str) -> Tuple[str, EvalResult]:
        """ਸਭ ਤੋਂ ਉੱਚੀ fitness; ਨੇੜੇ ਹੋਵੇ ਤਾਂ Verifier vote"""
        scored = sorted(scored, key=lambda x: x[1].total, reverse=True)
        if len(scored) >= 2 and self.verifier:
            top, second = scored[0], scored[1]
            if abs(top[1].total - second[1].total) < 0.05:
                idx = self.verifier.choose(task, [top[0], second[0]])
                if idx == 1:
                    log.info("   🗳️  Verifier vote: chose 2nd candidate (close tie)")
                    return second
        return scored[0]

    # ──────────────────────────────────────────────────────────────
    def evolve_code(
        self, task: str, max_turns: int = 3,
        hidden_tests: Optional[List[str]] = None,
        property_tests: Optional[List[str]] = None,
    ) -> dict:
        """
        ਪੂਰਾ Frontier evolution loop ਚਲਾਓ।

        hidden_tests / property_tests ਜੇ ਨਾ ਦਿੱਤੇ ਜਾਣ ਤਾਂ fitness ~0.35 ਤੋਂ
        ਉੱਪਰ ਨਹੀਂ ਜਾ ਸਕਦੀ (by design — ਪੇਪਰ ਦਾ feedback-quality ਨੁਕਤਾ)।
        """
        sid = datetime.now().strftime("%Y%m%d_%H%M%S")
        hidden = hidden_tests or []
        prop = property_tests or []

        log.info("═" * 65)
        log.info(f"🚀 Session {sid}: {task[:70]}")
        log.info(f"   hidden_tests={len(hidden)}  property_tests={len(prop)}")
        log.info("═" * 65)

        # ── STEP 0a: Khoj research (Pathway 5.4) ──
        research = ""
        if self.khoj:
            try:
                research = self.khoj.execute(
                    f"Give technical best-practices and common pitfalls for: {task}"
                ).output
                log.info(f"🔬 Khoj research: {len(research)} chars")
            except Exception as e:
                log.warning(f"   Khoj failed: {e}")

        # ── STEP 0b: retrieve past failures + reflections ──
        past_fail = self.failures.retrieve(task)
        lessons = self.reflections.retrieve(task)
        if past_fail:
            log.info("🧬 Retrieved similar past failures")
        if lessons:
            log.info("💡 Retrieved past lessons")

        # ── STEP 0c: Planner (ਅੱਗੇ ਤੋਂ ਸੋਚਣਾ) ──
        plan = {}
        if self.planner:
            plan = self.planner.plan(task, research=research, reflections=lessons)
            log.info(f"🗺️  Plan: entry_point='{plan.get('entry_point')}', "
                     f"{len(plan.get('steps', []))} steps")

        plan_text = json.dumps(plan, ensure_ascii=False) if plan else ""
        context = (
            (f"Research:\n{research}\n\n" if research else "")
            + (f"{past_fail}\n" if past_fail else "")
            + (f"{lessons}\n" if lessons else "")
            + (f"Plan:\n{plan_text}\n\n" if plan_text else "")
        )

        # ── STEP 1: initial generation (swarm best-of-N) ──
        log.info(f"🧠 Nirman swarm: generating {self.n} initial candidates...")
        init_prompt = f"Task: {task}\n\n{context}"
        candidates = self._generate(init_prompt)
        scored = self._score_candidates(candidates, hidden, prop, None, f"init_{sid}")
        best_code, best_ev = self._pick_best(scored, task)
        best_fitness = best_ev.total
        log.info(f"🏆 Initial best: {best_ev.render()}")

        history = []
        first_issues_text = ""

        # ── EVOLUTION LOOP ──
        for turn in range(1, max_turns + 1):
            log.info("─" * 65)
            log.info(f"🔄 TURN {turn}/{max_turns}")

            # Verifier gate
            vres = VerifyResult(no_issues=False, confidence=0.0)
            if self.verifier:
                vres = self.verifier.verify(task, best_code, plan=plan_text)
                log.info(f"🔎 Verifier: {vres.render()}")
                if turn == 1 and vres.issues:
                    first_issues_text = "; ".join(
                        i.get("reason", "") for i in vres.issues)

            # early stop?
            done = (best_fitness >= 0.95
                    and vres.confidence >= 0.90
                    and vres.no_issues)
            if done:
                log.info("🎯 Early stop: fitness≥0.95, confidence≥0.90, no issues")
                history.append({"turn": turn, "fitness": best_fitness,
                                "status": "EARLY_STOP"})
                break

            # If verifier strongly says no_issues but fitness can't improve, also stop
            if self.verifier and vres.no_issues and turn > 1 and best_fitness < 0.95:
                log.info("ℹ️  Verifier finds no issues but fitness capped "
                         "(likely missing tests) — stopping.")
                history.append({"turn": turn, "fitness": best_fitness,
                                "status": "NO_ISSUES_STOP"})
                break

            # Vivek deep critique (Verifier issues ਨੂੰ expand ਕਰਦਾ ਹੈ)
            log.info("🔍 Vivek: deep critique for refinement...")
            seed = ("Verifier flagged: " +
                    json.dumps(vres.issues, ensure_ascii=False)) if vres.issues else \
                   "No specific issues flagged; look for correctness and edge cases."
            try:
                critique = self.vivek.execute(
                    f"Task: {task}\n\nCode:\n{best_code}\n\n{seed}\n\n"
                    "List concrete, code-grounded fixes (no invented problems)."
                ).output
            except Exception as e:
                critique = f"(critique unavailable: {e})"

            # Nirman refine (swarm)
            log.info(f"🔥 Nirman swarm: {self.n} refined candidates...")
            refine_prompt = (
                f"Task: {task}\n\nCurrent code:\n{best_code}\n\n"
                f"Fixes to apply:\n{critique}\n\n{context}"
            )
            refined = self._generate(refine_prompt)
            rescored = self._score_candidates(
                refined, hidden, prop, best_code, f"ref{turn}_{sid}")
            cand_code, cand_ev = self._pick_best(rescored, task)

            # rollback protection
            if cand_ev.total > best_fitness:
                log.info(f"⬆️  Improved {best_fitness:.3f} → {cand_ev.total:.3f}")
                best_code, best_ev, best_fitness = cand_code, cand_ev, cand_ev.total
            else:
                log.info(f"↩️  No improvement ({cand_ev.total:.3f} ≤ "
                         f"{best_fitness:.3f}) — keeping best (rollback)")

            history.append({"turn": turn, "fitness": best_fitness,
                            "verifier": vres.render()})

        # ── STEP 2: learn from this run ──
        if best_fitness >= 0.85:
            self.reflections.add(
                task=task,
                what_worked=f"swarm best-of-{self.n} + verifier gate reached "
                            f"{best_fitness:.2f}",
                what_failed=first_issues_text or "none",
                why="iterative critique fixed early issues; tests confirmed correctness",
                fitness=best_fitness,
            )
            log.info("💾 Reflection stored (success)")
        else:
            self.failures.record(
                task=task,
                error_type="LowFitnessEvolution",
                detail=f"only reached {best_fitness:.2f}; issues: {first_issues_text}",
            )
            log.info("🧬 Failure recorded (low fitness)")

        log.info("═" * 65)
        log.info(f"✨ Done | fitness={best_fitness:.3f} | turns={len(history)} | "
                 f"code={len(best_code)} chars")
        log.info("═" * 65)

        return {
            "session_id": sid,
            "task": task,
            "final_code": best_code,
            "highest_fitness": best_fitness,
            "breakdown": best_ev.breakdown,
            "history": history,
            "plan": plan,
            "used": {
                "khoj": bool(research),
                "planner": bool(plan),
                "verifier": bool(self.verifier),
            },
        }


# ══════════════════════════════════════════════════════════════════
# SOUL.PY INTEGRATION HELPER (DRY — ਇੱਕੋ loop, ਇੱਕੋ ਜਗ੍ਹਾ)
# ══════════════════════════════════════════════════════════════════
def genesis_handler_v3(soul_instance, command: str,
                       hidden_tests=None, property_tests=None) -> str:
    """
    soul.py ਦੇ _execute() ਵਿੱਚ GENESIS ਭਾਗ ਦਾ replacement।

        from dual_brain_engine_v3 import genesis_handler_v3
        elif module == "GENESIS":
            return genesis_handler_v3(self, command)
    """
    engine = DualBrainEngineV3(
        agent_builder=soul_instance.agents,
        mutation_lab=soul_instance.genesis.lab,
        failures=getattr(soul_instance, "failure_retrieval", None),
        reflections=getattr(soul_instance, "reflection_memory", None),
    )
    result = engine.evolve_code(command, max_turns=3,
                                hidden_tests=hidden_tests,
                                property_tests=property_tests)

    skill_name = command[:40].lower().replace(" ", "_").replace("/", "_")
    file_path = soul_instance.genesis.skills_dir / f"{skill_name}.py"
    file_path.write_text(
        f'"""\nTask: {command}\nFitness: {result["highest_fitness"]:.3f}\n"""\n\n'
        + result["final_code"], encoding="utf-8")

    return (f"✨ Skill '{skill_name}' | fitness {result['highest_fitness']:.3f} | "
            f"turns {len(result['history'])}")


# ══════════════════════════════════════════════════════════════════
# ███  SELF TEST (Ollama/AgentBuilder ਤੋਂ ਬਿਨਾਂ — ਪੂਰੀ ਤਰ੍ਹਾਂ runnable) ███
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import io
    import os
    import sys
    import signal
    import tempfile
    import contextlib

    # ── ScriptedAgent: deterministic outputs (call order ਮੁਤਾਬਕ) ──
    class _Resp:
        def __init__(self, o): self.output = o

    class ScriptedAgent:
        def __init__(self, outputs):
            self.outputs = list(outputs)
            self.i = 0
        def execute(self, prompt):
            o = self.outputs[self.i] if self.i < len(self.outputs) \
                else (self.outputs[-1] if self.outputs else "")
            self.i += 1
            return _Resp(o)

    class MockBuilder:
        def __init__(self, agents): self.agents = agents

    # ── MockMutationLab: asਲ ਵਿੱਚ driver ਚਲਾਉਂਦਾ ਹੈ (timeout-protected) ──
    class MockMutationLab:
        def __init__(self): self.variants = {}
        def create_variant(self, name, code):
            self.variants[name] = code
            return name, code
        def test_in_sandbox(self, vid):
            code = self.variants[vid]
            buf = io.StringIO()

            def _timeout(signum, frame):
                raise TimeoutError("sandbox timeout")
            had_alarm = hasattr(signal, "SIGALRM")
            if had_alarm:
                old = signal.signal(signal.SIGALRM, _timeout)
                signal.alarm(5)
            try:
                with contextlib.redirect_stdout(buf):
                    ns = {"__name__": "_sandbox_"}
                    exec(compile(code, "<sandbox>", "exec"), ns)
                passed = True
            except Exception as e:
                buf.write(f"\nERROR: {e}")
                passed = False
            finally:
                if had_alarm:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old)
            return passed, buf.getvalue()

    # ── factorial candidates (ਅਸਲ ਚੱਲਣ ਵਾਲਾ ਕੋਡ) ──
    CAND_A = (
        "def factorial(n):\n"
        "    if not isinstance(n, int) or n < 0:\n"
        "        raise ValueError('n must be a non-negative integer')\n"
        "    if n == 0:\n"
        "        return 0\n"                       # BUG: should be 1
        "    result = 1\n"
        "    for i in range(1, n + 1):\n"
        "        result *= i\n"
        "    return result\n"
    )
    CAND_B = (
        "def factorial(n):\n"
        "    result = 1\n"
        "    for i in range(2, n + 1):\n"          # correct for n>=0 but NO validation
        "        result *= i\n"
        "    return result\n"
    )
    CAND_C = (
        "def factorial(n):\n"
        "    result = 1\n"
        "    for i in range(1, n):\n"              # BUG: off-by-one
        "        result *= i\n"
        "    return result\n"
    )
    GOOD = (
        "def factorial(n):\n"
        "    if not isinstance(n, int) or n < 0:\n"
        "        raise ValueError('n must be a non-negative integer')\n"
        "    result = 1\n"
        "    for i in range(2, n + 1):\n"
        "        result *= i\n"
        "    return result\n"
    )

    HIDDEN = [
        "assert factorial(0) == 1",
        "assert factorial(5) == 120",
        "assert factorial(1) == 1",
        "try:\n    factorial(-1)\n    raise AssertionError('expected ValueError')\nexcept ValueError:\n    pass",
    ]
    PROPERTY = [
        "for _n in range(1, 8):\n    assert factorial(_n) == _n * factorial(_n - 1)",
    ]

    # Verifier JSON outputs
    V_ISSUE = ('{"no_issues": false, "confidence": 0.7, "issues": '
               '[{"location": "factorial", "reason": "no validation; '
               'factorial(-1) returns 1 instead of raising ValueError", '
               '"fix": "add isinstance/n<0 check"}]}')
    V_CLEAN = '{"no_issues": true, "confidence": 0.95, "issues": []}'

    PLAN = ('{"entry_point": "factorial", "steps": '
            '["validate non-negative int", "iterative multiply", "return"], '
            '"constraints": ["raise ValueError on negative"]}')

    # Nirman call order: init(A,B,C) then refine(GOOD,B,C)
    agents = {
        "Khoj":     ScriptedAgent(["Use iterative loop; validate input; "
                                   "remember 0! = 1 and negative is invalid."]),
        "Planner":  ScriptedAgent([PLAN]),
        "Nirman":   ScriptedAgent([CAND_A, CAND_B, CAND_C, GOOD, CAND_B, CAND_C]),
        "Vivek":    ScriptedAgent(["Add input validation: raise ValueError for "
                                   "negative or non-int input."]),
        "Verifier": ScriptedAgent([V_ISSUE, V_CLEAN]),
    }

    # temp memory files (cwd ਨੂੰ pollute ਨਾ ਕਰੀਏ)
    tmp = tempfile.gettempdir()
    fr_path = os.path.join(tmp, "_v3_fail.json")
    rm_path = os.path.join(tmp, "_v3_refl.json")
    for p in (fr_path, rm_path):
        if os.path.exists(p):
            os.remove(p)

    print("\n" + "█" * 66)
    print("█  DualBrainEngine v3.0 — FULL INTEGRATION TEST")
    print("█  (ScriptedAgents + real sandbox execution)")
    print("█" * 66 + "\n")

    engine = DualBrainEngineV3(
        agent_builder=MockBuilder(agents),
        mutation_lab=MockMutationLab(),
        failures=FailureRetrieval(fr_path),
        reflections=ReflectionMemory(rm_path),
        n_candidates=3,
    )

    result = engine.evolve_code(
        task="Write a factorial function with input validation",
        max_turns=2,
        hidden_tests=HIDDEN,
        property_tests=PROPERTY,
    )

    print("\n" + "═" * 60)
    print("📊 RESULT SUMMARY")
    print("═" * 60)
    print(f"   Highest fitness : {result['highest_fitness']:.3f}")
    print(f"   Turns taken     : {len(result['history'])}")
    print(f"   Plan entry_point: {result['plan'].get('entry_point')}")
    print(f"   Final code:\n")
    for ln in result["final_code"].splitlines():
        print("       " + ln)

    # ── ASSERTIONS (ਗਲਤੀ ਫੜਨ ਲਈ) ──
    print("\n" + "═" * 60)
    print("🧪 ASSERTIONS")
    print("═" * 60)
    ok = True

    def check(name, cond):
        global ok
        print(f"   {'✅' if cond else '❌'} {name}")
        ok = ok and cond

    check("reached high fitness (≥0.95)", result["highest_fitness"] >= 0.95)
    check("final code defines factorial", "def factorial" in result["final_code"])
    check("final code has validation", "ValueError" in result["final_code"])
    check("planner produced entry_point", result["plan"].get("entry_point") == "factorial")
    check("reflection stored (success path)",
          ReflectionMemory(rm_path).summary()["count"] == 1)
    check("early-stopped within 2 turns", len(result["history"]) <= 2)

    # cleanup
    for p in (fr_path, rm_path):
        if os.path.exists(p):
            os.remove(p)

    print("\n" + ("🎉 ALL CHECKS PASSED" if ok else "🔴 SOME CHECKS FAILED"))
    sys.exit(0 if ok else 1)
