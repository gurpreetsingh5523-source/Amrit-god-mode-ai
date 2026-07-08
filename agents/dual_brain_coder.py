"""
dual_brain_coder.py — DualBrain v3 wired into God Mode's coding pipeline.

Upgrades coder_agent from "generate once" to:
  1. Swarm: 3 candidates simultaneously (correctness / simplicity / robustness)
  2. Auto-test: TestWriter generates hidden + property tests from spec
  3. Fitness score: 45% tests + 20% properties + 15% syntax + 10% sandbox + 10% security
  4. Verifier: rejects hallucinated bugs before iterating
  5. Learns: ReflectionMemory stores what worked; FailureRetrieval avoids past mistakes
  6. Early-stop: quits at fitness ≥ 0.95 — no wasted cycles

Usage (from any agent or orchestrator):
    from dual_brain_coder import evolve_code, DualBrainCoder
    result = evolve_code("write a JWT auth FastAPI endpoint")
    print(result["final_code"])
    print(f"Fitness: {result['highest_fitness']:.2f}")
"""

from pathlib import Path
from logger import setup_logger

logger = setup_logger("DualBrainCoder")

# Persistent memory paths
_FAILURES_PATH    = "workspace/dual_brain/failures.json"
_REFLECTIONS_PATH = "workspace/dual_brain/reflections.json"


def _build_agent_builder():
    """Build AgentBuilder with qwen3.5:9b for all roles."""
    from llm_client import LLMClient

    def _make(role_prompt):
        return LLMClient(system_prompt=role_prompt)

    NIRMAN_PROMPT = (
        "You are Nirman — an elite software engineer. "
        "You write complete, correct, production-ready Python code. "
        "Output ONLY executable Python. No markdown fences, no explanation."
    )
    VIVEK_PROMPT = (
        "You are Vivek — a strict code reviewer. "
        "Find real, concrete bugs only. "
        "Never invent problems. Be specific: line numbers and exact fixes."
    )
    KHOJ_PROMPT = (
        "You are Khoj — a technical researcher. "
        "Provide best practices, edge cases, and known pitfalls for the given task. "
        "Be concise and code-focused."
    )
    PLANNER_PROMPT = (
        "You are a software architect. "
        "Decompose coding tasks into entry-point, steps, and constraints. "
        "Output JSON only."
    )
    VERIFIER_PROMPT = (
        "You are a code verifier. "
        "Find 0-3 real issues in the code. Never hallucinate bugs. "
        "Output JSON only: {no_issues, confidence, issues:[{location,reason,fix}]}"
    )
    TESTWRITER_PROMPT = (
        "You are a test engineer. "
        "Write hidden tests and property tests for a task spec. "
        "Tests must be independent of any candidate's implementation. "
        "Output JSON: {hidden_tests:[str], property_tests:[str]}"
    )

    class _SimpleBuilder:
        """Minimal builder — no SQLite needed, uses LLMClient directly."""
        def __init__(self):
            self.agents = {
                "Nirman":     _make(NIRMAN_PROMPT),
                "Vivek":      _make(VIVEK_PROMPT),
                "Khoj":       _make(KHOJ_PROMPT),
                "Planner":    _make(PLANNER_PROMPT),
                "Verifier":   _make(VERIFIER_PROMPT),
                "TestWriter": _make(TESTWRITER_PROMPT),
            }

    return _SimpleBuilder()


def evolve_code(task: str, max_turns: int = 3,
                hidden_tests=None, property_tests=None) -> dict:
    """
    Main entry point. Run DualBrain v3 on a coding task.

    Returns:
        dict with keys: final_code, highest_fitness, history, plan,
                        tests_used, breakdown, session_id
    """
    try:
        from dual_brain_engine_v3 import DualBrainEngineV3
        from failure_retrieval import FailureRetrieval
        from reflection_memory import ReflectionMemory

        Path("workspace/dual_brain").mkdir(parents=True, exist_ok=True)

        engine = DualBrainEngineV3(
            agent_builder=_build_agent_builder(),
            mutation_lab=None,
            failures=FailureRetrieval(_FAILURES_PATH),
            reflections=ReflectionMemory(_REFLECTIONS_PATH),
            n_candidates=3,
            sandbox_timeout=15,
        )
        return engine.evolve_code(task, max_turns=max_turns,
                                  hidden_tests=hidden_tests,
                                  property_tests=property_tests)
    except Exception as e:
        logger.error(f"DualBrain failed: {e}")
        return {"error": str(e), "final_code": "", "highest_fitness": 0.0}


class DualBrainCoder:
    """
    God Mode agent wrapper — drop-in upgrade for coder_agent's
    complex coding tasks.
    """

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from dual_brain_engine_v3 import DualBrainEngineV3
            from failure_retrieval import FailureRetrieval
            from reflection_memory import ReflectionMemory
            Path("workspace/dual_brain").mkdir(parents=True, exist_ok=True)
            self._engine = DualBrainEngineV3(
                agent_builder=_build_agent_builder(),
                mutation_lab=None,
                failures=FailureRetrieval(_FAILURES_PATH),
                reflections=ReflectionMemory(_REFLECTIONS_PATH),
                n_candidates=3,
                sandbox_timeout=15,
            )
        return self._engine

    def code(self, task: str, max_turns: int = 3) -> dict:
        """Evolve code for a task. Returns result dict."""
        try:
            return self._get_engine().evolve_code(task, max_turns=max_turns)
        except Exception as e:
            logger.error(f"DualBrainCoder.code failed: {e}")
            return {"error": str(e), "final_code": "", "highest_fitness": 0.0}

    def quick_code(self, task: str) -> str:
        """1-turn fast generation — returns code string only."""
        result = self.code(task, max_turns=1)
        return result.get("final_code", "")

    def status(self) -> dict:
        """Check if DualBrain engine is available."""
        try:
            from dual_brain_engine_v3 import DualBrainEngineV3
            from failure_retrieval import FailureRetrieval
            from reflection_memory import ReflectionMemory
            from multi_evaluator import evaluate
            from verifier import VerifierAgent
            from planner import PlannerAgent
            from test_writer import TestWriterAgent
            from security_guard import SecurityGuard
            return {
                "available": True,
                "components": {
                    "DualBrainEngineV3": "✅",
                    "FailureRetrieval": "✅",
                    "ReflectionMemory": "✅",
                    "MultiEvaluator": "✅",
                    "Verifier": "✅",
                    "Planner": "✅",
                    "TestWriter": "✅",
                    "SecurityGuard": "✅",
                }
            }
        except ImportError as e:
            return {"available": False, "error": str(e)}
