#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║  🧠 dual_brain_engine_v3.py — Frontier Edition (v3.1)               ║
║                                                                      ║
║  Google DeepMind "From AGI to ASI" (arXiv:2606.12683, Genewein 2026)║
║  ਦੇ ਚਾਰ pathways ਵਿੱਚੋਂ ਦੋ ਨੂੰ ਅਮਲ ਵਿੱਚ ਲਿਆਉਂਦਾ ਹੈ:               ║
║    • §5.3 — Recursive Self-Improvement                              ║
║    • §5.4 — Multi-Agent Collective (swarm)                          ║
║  ਅਤੇ §5.5 frictions ਦਾ ਜਵਾਬ: feedback quality, echo-chamber,        ║
║  safety/control।                                                     ║
║                                                                      ║
║  ── v3.1 ਵਿੱਚ ਨਵਾਂ ──                                              ║
║  • Lab-agnostic sandbox: ਤੁਹਾਡੀ MutationLab ਦੇ interface 'ਤੇ        ║
║    ਨਿਰਭਰ ਨਹੀਂ। ਜੇ lab ਕੋਲ਼ run_in_sandbox() ਹੈ ਤਾਂ ਵਰਤਦਾ ਹੈ,        ║
║    ਨਹੀਂ ਤਾਂ ਆਪਣਾ subprocess sandbox (ਪੂਰਾ stdout, timeout)।         ║
║  • TestWriter integration: tests ਨਾ ਹੋਣ 'ਤੇ ਆਪੇ ਬਣਾਉਂਦਾ ਹੈ          ║
║    (0.35 fitness barrier ਤੋੜਦਾ ਹੈ)।                                 ║
║                                                                      ║
║  ਨੋਟ (ਇਮਾਨਦਾਰੀ): ਪੇਪਰ pathways/frictions ਨੂੰ open research          ║
║  questions ਵਜੋਂ ਪੇਸ਼ ਕਰਦਾ ਹੈ — ਹੇਠਲੇ ਫੈਸਲੇ ਉਸ ਤੋਂ "ਪ੍ਰੇਰਿਤ" ਹਨ।    ║
╚══════════════════════════════════════════════════════════════════════╝

ਪੂਰਾ flow:
    Khoj → FailureRetrieval → ReflectionMemory → Planner → TestWriter
      → Loop:
          Nirman A/B/C (swarm) → SecurityGuard → Sandbox(+tests)
            → multi_evaluator → best (Verifier vote)
          → Verifier (0–3 issues, validity, confidence)
          → early-stop? (fitness≥0.95 AND confidence≥0.90 AND no_issues)
          → Vivek critique → Nirman refine
      → ReflectionMemory.add (ਸਫ਼ਲ) / FailureRetrieval.record (ਅਸਫ਼ਲ)
"""

import os
import sys
import json
import logging
import tempfile
import subprocess
from datetime import datetime
from typing import List, Optional, Tuple

from security_guard import SecurityGuard
from multi_evaluator import evaluate, EvalResult
from failure_retrieval import FailureRetrieval
from reflection_memory import ReflectionMemory
from planner import PlannerAgent
from verifier import VerifierAgent, VerifyResult

try:
    from test_writer import TestWriterAgent
except Exception:
    TestWriterAgent = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("DualBrainV3")


# ══════════════════════════════════════════════════════════════════
# SANDBOX (subprocess, ਪੂਰਾ stdout — __EVAL_JSON__ ਕੱਟਿਆ ਨਹੀਂ ਜਾਂਦਾ)
# ══════════════════════════════════════════════════════════════════
def run_python_subprocess(code: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    ਕੋਡ ਨੂੰ ਵੱਖਰੇ python process ਵਿੱਚ ਚਲਾਓ ਅਤੇ ਪੂਰਾ stdout ਵਾਪਸ ਕਰੋ।
    Returns: (ran_ok, full_output)
    """
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False,
                                    encoding="utf-8")
    path = f.name
    try:
        f.write(code)
        f.flush()
        f.close()
        r = subprocess.run([sys.executable, path],
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "")
        if r.stderr:
            out += "\nSTDERR:\n" + r.stderr
        return (r.returncode == 0), out
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"sandbox error: {e}"
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
# TEST DRIVER BUILDER
# candidate + hidden/property tests → self-contained script ਜੋ ਅੰਤ ਵਿੱਚ
# __EVAL_JSON__ marker ਨਾਲ ਨਤੀਜਾ print ਕਰਦਾ ਹੈ।
# candidate ਨੂੰ ਵੱਖਰੇ namespace ਵਿੱਚ ਚਲਾਉਂਦਾ ਹੈ (__main__ guard ਨਾ ਚੱਲੇ)।
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
    Parameters:
        agent_builder  : AgentBuilder (agents: Nirman, Vivek, Khoj,
                         + ਨਵੇਂ Planner, Verifier, TestWriter)
        mutation_lab   : optional — ਜੇ ਇਸ ਕੋਲ਼ run_in_sandbox(code, timeout)
                         ਹੋਵੇ ਤਾਂ ਵਰਤਿਆ ਜਾਂਦਾ ਹੈ; ਨਹੀਂ ਤਾਂ built-in subprocess
                         sandbox ਵਰਤਦਾ ਹੈ। None ਵੀ ਠੀਕ ਹੈ।
        failures       : FailureRetrieval (optional)
        reflections    : ReflectionMemory (optional)
        n_candidates   : best-of-N swarm size (default 3)
        sandbox_timeout: ਹਰ candidate ਲਈ ਵੱਧ ਤੋਂ ਵੱਧ seconds
    """

    VARIANT_HINTS = [
        "Prioritize correctness and edge cases.",
        "Prioritize simplicity and readability.",
        "Prioritize robustness and input validation.",
    ]

    def __init__(self, agent_builder, mutation_lab=None,
                 failures: Optional[FailureRetrieval] = None,
                 reflections: Optional[ReflectionMemory] = None,
                 n_candidates: int = 3, sandbox_timeout: int = 10):
        self.builder = agent_builder
        self.lab = mutation_lab
        self.failures = failures or FailureRetrieval()
        self.reflections = reflections or ReflectionMemory()
        self.n = max(1, n_candidates)
        self.timeout = sandbox_timeout
        self.guard = SecurityGuard()

        agents = agent_builder.agents
        self.nirman = agents["Nirman"]            # ਲਾਜ਼ਮੀ
        self.vivek = agents["Vivek"]              # ਲਾਜ਼ਮੀ
        self.khoj = agents.get("Khoj")            # ਵਿਕਲਪਿਕ
        self.planner = PlannerAgent(agents["Planner"]) if "Planner" in agents else None
        self.verifier = VerifierAgent(agents["Verifier"]) if "Verifier" in agents else None
        self.test_writer = (TestWriterAgent(agents["TestWriter"])
                            if TestWriterAgent and "TestWriter" in agents else None)

        lab_mode = ("lab.run_in_sandbox" if (self.lab is not None and
                    hasattr(self.lab, "run_in_sandbox")) else "built-in subprocess")
        log.info("🧠 DualBrainEngine v3.1 (Frontier) — Ready")
        log.info(f"   Swarm size : {self.n} (Nirman A/B/C…)")
        log.info(f"   Sandbox    : {lab_mode}")
        log.info(f"   Khoj       : {'✅' if self.khoj else '—'}  "
                 f"Planner: {'✅' if self.planner else '—'}  "
                 f"Verifier: {'✅' if self.verifier else '—'}  "
                 f"TestWriter: {'✅' if self.test_writer else '—'}")

    # ──────────────────────────────────────────────────────────────
    def _sandbox(self, code: str) -> Tuple[bool, str]:
        """lab ਹੋਵੇ ਤਾਂ ਉਹ, ਨਹੀਂ ਤਾਂ built-in subprocess"""
        if self.lab is not None and hasattr(self.lab, "run_in_sandbox"):
            try:
                return self.lab.run_in_sandbox(code, self.timeout)
            except Exception as e:
                return False, f"lab error: {e}"
        return run_python_subprocess(code, self.timeout)

    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _strip_fences(code: str) -> str:
        """Remove markdown code fences (```python ... ```) so the sandbox can
        actually run/parse the candidate. LLMs often wrap code in fences."""
        import re as _re
        if not code:
            return code
        s = code.strip()
        # Opening fence with optional language tag
        s = _re.sub(r'^```[a-zA-Z0-9_+\-]*\s*\n', '', s)
        # Closing fence
        s = _re.sub(r'\n```\s*$', '', s)
        s = _re.sub(r'^```\s*$', '', s, flags=_re.MULTILINE)
        return s.strip()

    def _generate(self, base_prompt: str) -> List[str]:
        out = []
        for i in range(self.n):
            hint = self.VARIANT_HINTS[i % len(self.VARIANT_HINTS)]
            prompt = (base_prompt + f"\n\nStrategy: {hint}\n"
                      "Output ONLY complete, executable Python code. No explanations.")
            try:
                out.append(self._strip_fences(self.nirman.execute(prompt).output))
            except Exception as e:
                log.error(f"   Nirman candidate {i} failed: {e}")
                out.append("")
        return out

    # ──────────────────────────────────────────────────────────────
    def _score_candidates(self, candidates, hidden, prop, previous_code, tag):
        results = []
        for i, cand in enumerate(candidates):
            safe, findings = self.guard.scan(cand)
            if not safe:
                log.info(f"   [{tag}#{i}] 🚫 blocked: {findings[0] if findings else '?'}")
                results.append((cand, EvalResult(0.0, {"security": 0.0}, False, "blocked")))
                continue

            driver = build_test_driver(cand, hidden, prop)
            ran, output = self._sandbox(driver)

            res_json = parse_eval(output)
            if res_json and res_json.get("load_ok"):
                hp, ht = res_json["hidden_pass"], res_json["hidden_total"]
                pp, pt = res_json["property_pass"], res_json["property_total"]
                sandbox_ran = bool(ran)
            else:
                hp, ht = 0, len(hidden or [])
                pp, pt = 0, len(prop or [])
                sandbox_ran = False

            ev = evaluate(cand, security_ok=True, sandbox_ran=sandbox_ran,
                          hidden=(hp, ht), prop=(pp, pt), previous_code=previous_code)
            log.info(f"   [{tag}#{i}] {ev.render()}")
            results.append((cand, ev))
        return results

    # ──────────────────────────────────────────────────────────────
    def _pick_best(self, scored, task):
        scored = sorted(scored, key=lambda x: x[1].total, reverse=True)
        if len(scored) >= 2 and self.verifier:
            top, second = scored[0], scored[1]
            if abs(top[1].total - second[1].total) < 0.05:
                idx = self.verifier.choose(task, [top[0], second[0]])
                if idx == 1:
                    log.info("   🗳️  Verifier vote: chose 2nd (close tie)")
                    return second
        return scored[0]

    # ──────────────────────────────────────────────────────────────
    def evolve_code(self, task: str, max_turns: int = 3,
                    hidden_tests: Optional[List[str]] = None,
                    property_tests: Optional[List[str]] = None) -> dict:
        sid = datetime.now().strftime("%Y%m%d_%H%M%S")
        hidden = list(hidden_tests or [])
        prop = list(property_tests or [])

        log.info("═" * 65)
        log.info(f"🚀 Session {sid}: {task[:70]}")
        log.info("═" * 65)

        # STEP 0a: Khoj research
        research = ""
        if self.khoj:
            try:
                research = self.khoj.execute(
                    f"Give technical best-practices and common pitfalls for: {task}"
                ).output
                log.info(f"🔬 Khoj research: {len(research)} chars")
            except Exception as e:
                log.warning(f"   Khoj failed: {e}")

        # STEP 0b: retrieve past failures + reflections
        past_fail = self.failures.retrieve(task)
        lessons = self.reflections.retrieve(task)
        if past_fail:
            log.info("🧬 Retrieved similar past failures")
        if lessons:
            log.info("💡 Retrieved past lessons")

        # STEP 0c: Planner
        plan = {}
        if self.planner:
            plan = self.planner.plan(task, research=research, reflections=lessons)
            log.info(f"🗺️  Plan: entry_point='{plan.get('entry_point')}', "
                     f"{len(plan.get('steps', []))} steps")
        plan_text = json.dumps(plan, ensure_ascii=False) if plan else ""
        entry_point = plan.get("entry_point", "solution") if plan else "solution"

        # STEP 0d: TestWriter (ਜੇ tests ਨਾ ਦਿੱਤੇ ਗਏ — 0.35 barrier ਤੋੜੂ)
        if not hidden and not prop and self.test_writer:
            log.info("🧪 TestWriter: generating hidden + property tests...")
            gen_h, gen_p = self.test_writer.write_tests(task, plan_text, entry_point)
            # ਸੁਰੱਖਿਆ: ਹਰ generated test ਨੂੰ ਵੀ scan ਕਰੋ (LLM ਖ਼ਤਰਨਾਕ ਲਿਖ ਸਕਦਾ)
            hidden = [t for t in gen_h if self.guard.scan(t)[0]]
            prop = [t for t in gen_p if self.guard.scan(t)[0]]
            log.info(f"   → {len(hidden)} hidden + {len(prop)} property tests "
                     f"(after security scan)")
        if not hidden and not prop:
            log.warning("⚠️  ਕੋਈ tests ਨਹੀਂ — fitness ~0.35 'ਤੇ capped ਰਹੇਗੀ।")

        context = (
            (f"Research:\n{research}\n\n" if research else "")
            + (f"{past_fail}\n" if past_fail else "")
            + (f"{lessons}\n" if lessons else "")
            + (f"Plan:\n{plan_text}\n\n" if plan_text else "")
        )

        # STEP 1: initial swarm
        log.info(f"🧠 Nirman swarm: {self.n} initial candidates...")
        candidates = self._generate(f"Task: {task}\n\n{context}")
        scored = self._score_candidates(candidates, hidden, prop, None, f"init_{sid}")
        best_code, best_ev = self._pick_best(scored, task)
        best_fitness = best_ev.total
        log.info(f"🏆 Initial best: {best_ev.render()}")

        history = []
        first_issues_text = ""

        # EVOLUTION LOOP
        for turn in range(1, max_turns + 1):
            log.info("─" * 65)
            log.info(f"🔄 TURN {turn}/{max_turns}")

            vres = VerifyResult(no_issues=False, confidence=0.0)
            if self.verifier:
                vres = self.verifier.verify(task, best_code, plan=plan_text)
                log.info(f"🔎 Verifier: {vres.render()}")
                if turn == 1 and vres.issues:
                    first_issues_text = "; ".join(i.get("reason", "") for i in vres.issues)

            if best_fitness >= 0.95 and vres.confidence >= 0.90 and vres.no_issues:
                log.info("🎯 Early stop: fitness≥0.95, confidence≥0.90, no issues")
                history.append({"turn": turn, "fitness": best_fitness, "status": "EARLY_STOP"})
                break

            if self.verifier and vres.no_issues and turn > 1 and best_fitness < 0.95:
                log.info("ℹ️  No issues but fitness capped (likely missing tests) — stopping.")
                history.append({"turn": turn, "fitness": best_fitness, "status": "NO_ISSUES_STOP"})
                break

            log.info("🔍 Vivek: deep critique...")
            seed = ("Verifier flagged: " + json.dumps(vres.issues, ensure_ascii=False)
                    if vres.issues else "Look for correctness and edge-case bugs.")
            try:
                critique = self.vivek.execute(
                    f"Task: {task}\n\nCode:\n{best_code}\n\n{seed}\n\n"
                    "List concrete, code-grounded fixes (no invented problems)."
                ).output
            except Exception as e:
                critique = f"(critique unavailable: {e})"

            log.info(f"🔥 Nirman swarm: {self.n} refined candidates...")
            refined = self._generate(
                f"Task: {task}\n\nCurrent code:\n{best_code}\n\n"
                f"Fixes to apply:\n{critique}\n\n{context}")
            rescored = self._score_candidates(refined, hidden, prop, best_code, f"ref{turn}_{sid}")
            cand_code, cand_ev = self._pick_best(rescored, task)

            if cand_ev.total > best_fitness:
                log.info(f"⬆️  Improved {best_fitness:.3f} → {cand_ev.total:.3f}")
                best_code, best_ev, best_fitness = cand_code, cand_ev, cand_ev.total
            else:
                log.info(f"↩️  No improvement ({cand_ev.total:.3f} ≤ {best_fitness:.3f}) "
                         f"— keeping best (rollback)")

            history.append({"turn": turn, "fitness": best_fitness, "verifier": vres.render()})

        # STEP 2: learn
        if best_fitness >= 0.85:
            self.reflections.add(
                task=task,
                what_worked=f"swarm best-of-{self.n} + verifier gate reached {best_fitness:.2f}",
                what_failed=first_issues_text or "none",
                why="iterative critique fixed early issues; tests confirmed correctness",
                fitness=best_fitness)
            log.info("💾 Reflection stored (success)")
        else:
            self.failures.record(
                task=task, error_type="LowFitnessEvolution",
                detail=f"only reached {best_fitness:.2f}; issues: {first_issues_text}")
            log.info("🧬 Failure recorded (low fitness)")

        log.info("═" * 65)
        log.info(f"✨ Done | fitness={best_fitness:.3f} | turns={len(history)} | "
                 f"code={len(best_code)} chars")
        log.info("═" * 65)

        return {
            "session_id": sid, "task": task, "final_code": best_code,
            "highest_fitness": best_fitness, "breakdown": best_ev.breakdown,
            "history": history, "plan": plan,
            "tests_used": {"hidden": len(hidden), "property": len(prop)},
            "used": {"khoj": bool(research), "planner": bool(plan),
                     "verifier": bool(self.verifier), "test_writer": bool(self.test_writer)},
        }


# ══════════════════════════════════════════════════════════════════
# SOUL.PY INTEGRATION HELPER
# ══════════════════════════════════════════════════════════════════
def genesis_handler_v3(soul_instance, command: str,
                       hidden_tests=None, property_tests=None) -> str:
    """
    soul.py ਦੇ _execute() ਵਿੱਚ GENESIS ਭਾਗ ਦਾ replacement:

        from dual_brain_engine_v3 import genesis_handler_v3
        elif module == "GENESIS":
            return genesis_handler_v3(self, command)

    ਇਹ built-in subprocess sandbox ਵਰਤਦਾ ਹੈ (MutationLab ਦੀ ਲੋੜ ਨਹੀਂ),
    ਅਤੇ TestWriter ਨਾਲ tests ਆਪੇ ਬਣਾਉਂਦਾ ਹੈ।
    """
    from pathlib import Path

    engine = DualBrainEngineV3(
        agent_builder=soul_instance.agents,
        mutation_lab=getattr(getattr(soul_instance, "genesis", None), "lab", None),
        n_candidates=3,
    )
    result = engine.evolve_code(command, max_turns=3,
                                hidden_tests=hidden_tests, property_tests=property_tests)

    # skill ਸੇਵ ਕਰੋ (skills_dir ਜੇ ਹੈ, ਨਹੀਂ ਤਾਂ ./amrit_skills)
    skills_dir = getattr(getattr(soul_instance, "genesis", None), "skills_dir", None)
    if skills_dir is None:
        skills_dir = Path("./amrit_skills")
        skills_dir.mkdir(exist_ok=True)
    skill_name = command[:40].lower().replace(" ", "_").replace("/", "_")
    (Path(skills_dir) / f"{skill_name}.py").write_text(
        f'"""\nTask: {command}\nFitness: {result["highest_fitness"]:.3f}\n"""\n\n'
        + result["final_code"], encoding="utf-8")

    return (f"✨ Skill '{skill_name}' | fitness {result['highest_fitness']:.3f} | "
            f"turns {len(result['history'])} | "
            f"tests {result['tests_used']['hidden']}H+{result['tests_used']['property']}P")


# ══════════════════════════════════════════════════════════════════
# ███  SELF TEST (Ollama/AgentBuilder ਤੋਂ ਬਿਨਾਂ — ਪੂਰੀ ਤਰ੍ਹਾਂ runnable) ███
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import tempfile as _tf

    class _Resp:
        def __init__(self, o): self.output = o

    class ScriptedAgent:
        def __init__(self, outputs):
            self.outputs = list(outputs); self.i = 0
        def execute(self, prompt):
            o = self.outputs[self.i] if self.i < len(self.outputs) \
                else (self.outputs[-1] if self.outputs else "")
            self.i += 1
            return _Resp(o)

    class MockBuilder:
        def __init__(self, agents): self.agents = agents

    CAND_A = ("def factorial(n):\n"
              "    if not isinstance(n, int) or n < 0:\n"
              "        raise ValueError('n must be a non-negative integer')\n"
              "    if n == 0:\n"
              "        return 0\n"
              "    result = 1\n"
              "    for i in range(1, n + 1):\n"
              "        result *= i\n"
              "    return result\n")
    CAND_B = ("def factorial(n):\n"
              "    result = 1\n"
              "    for i in range(2, n + 1):\n"
              "        result *= i\n"
              "    return result\n")
    CAND_C = ("def factorial(n):\n"
              "    result = 1\n"
              "    for i in range(1, n):\n"
              "        result *= i\n"
              "    return result\n")
    GOOD = ("def factorial(n):\n"
            "    if not isinstance(n, int) or n < 0:\n"
            "        raise ValueError('n must be a non-negative integer')\n"
            "    result = 1\n"
            "    for i in range(2, n + 1):\n"
            "        result *= i\n"
            "    return result\n")

    HIDDEN = [
        "assert factorial(0) == 1",
        "assert factorial(5) == 120",
        "assert factorial(1) == 1",
        "try:\n    factorial(-1)\n    raise AssertionError('expected ValueError')\nexcept ValueError:\n    pass",
    ]
    PROPERTY = ["for _n in range(1, 8):\n    assert factorial(_n) == _n * factorial(_n - 1)"]

    V_ISSUE = ('{"no_issues": false, "confidence": 0.7, "issues": '
               '[{"location": "factorial", "reason": "no validation; factorial(-1) '
               'returns 1 instead of raising ValueError", "fix": "add isinstance/n<0 check"}]}')
    V_CLEAN = '{"no_issues": true, "confidence": 0.95, "issues": []}'
    PLAN = ('{"entry_point": "factorial", "steps": ["validate", "multiply", "return"], '
            '"constraints": ["raise ValueError on negative"]}')

    agents = {
        "Khoj":     ScriptedAgent(["Use iterative loop; 0!=1; negative invalid."]),
        "Planner":  ScriptedAgent([PLAN]),
        "Nirman":   ScriptedAgent([CAND_A, CAND_B, CAND_C, GOOD, CAND_B, CAND_C]),
        "Vivek":    ScriptedAgent(["Add input validation: ValueError for negative/non-int."]),
        "Verifier": ScriptedAgent([V_ISSUE, V_CLEAN]),
    }

    tmp = _tf.gettempdir()
    fr_path = os.path.join(tmp, "_v3_fail.json")
    rm_path = os.path.join(tmp, "_v3_refl.json")
    for p in (fr_path, rm_path):
        if os.path.exists(p):
            os.remove(p)

    print("\n" + "█" * 66)
    print("█  DualBrainEngine v3.1 — FULL INTEGRATION TEST")
    print("█  (ScriptedAgents + real subprocess sandbox, mutation_lab=None)")
    print("█" * 66 + "\n")

    engine = DualBrainEngineV3(
        agent_builder=MockBuilder(agents),
        mutation_lab=None,                     # built-in subprocess sandbox
        failures=FailureRetrieval(fr_path),
        reflections=ReflectionMemory(rm_path),
        n_candidates=3,
    )

    result = engine.evolve_code(
        task="Write a factorial function with input validation",
        max_turns=2, hidden_tests=HIDDEN, property_tests=PROPERTY)

    print("\n" + "═" * 60)
    print("📊 RESULT SUMMARY")
    print("═" * 60)
    print(f"   Highest fitness : {result['highest_fitness']:.3f}")
    print(f"   Turns taken     : {len(result['history'])}")
    print(f"   Plan entry_point: {result['plan'].get('entry_point')}")
    print(f"   Final code:\n")
    for ln in result["final_code"].splitlines():
        print("       " + ln)

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

    for p in (fr_path, rm_path):
        if os.path.exists(p):
            os.remove(p)

    print("\n" + ("🎉 ALL CHECKS PASSED" if ok else "🔴 SOME CHECKS FAILED"))
    sys.exit(0 if ok else 1)
