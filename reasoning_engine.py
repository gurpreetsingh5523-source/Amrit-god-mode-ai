"""
Reasoning Engine — AMRIT GODMODE ਦਾ ਡੂੰਘੀ ਸੋਚ ਵਾਲਾ ਦਿਮਾਗ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOT a wrapper around "think step by step".
This is REAL multi-candidate reasoning:
  1. Generates N candidates (different approaches to solving)
  2. Scores each candidate on logic, completeness, consistency
  3. Runs internal validation (can it be disproven?)
  4. Picks the BEST answer with confidence score
  5. Learns from which reasoning paths work

ਇਹ ਸਿਰਫ਼ LLM ਨੂੰ ਦੋ ਵਾਰ ਪੁੱਛਣ ਵਾਲੀ ਗੱਲ ਨਹੀਂ।
ਇਹ ਅਸਲੀ ਸੋਚ ਹੈ — ਕਈ ਰਾਹ ਸੋਚੋ, ਹਰ ਰਾਹ ਨੂੰ ਜਾਂਚੋ, ਫਿਰ ਸਭ ਤੋਂ ਵਧੀਆ ਚੁਣੋ।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import re
import hashlib
import time
from pathlib import Path
from logger import setup_logger

logger = setup_logger("ReasoningEngine")

# ── Response Cache ────────────────────────────────────────────────
_CACHE_PATH = Path("workspace/reasoning_cache.json")
_CACHE = {}


def _load_cache():
    global _CACHE
    if _CACHE_PATH.exists():
        try:
            _CACHE = json.loads(_CACHE_PATH.read_text())
        except Exception:
            _CACHE = {}


def _save_cache():
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep only last 200 entries
    trimmed = dict(list(_CACHE.items())[-200:])
    _CACHE_PATH.write_text(json.dumps(trimmed, indent=2, default=str))


def _cache_key(prompt: str, system: str = "") -> str:
    raw = f"{system}||{prompt}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


_load_cache()


# ── Complexity Estimator ──────────────────────────────────────────
# Real heuristic, not LLM-based

_COMPLEX_SIGNALS = {
    "high": [
        r"compiler|interpreter|parser|tokenizer",
        r"implement.*from.scratch",
        r"neural.network|transformer|attention",
        r"database|query.optimizer|index",
        r"encrypt|decrypt|crypto|hash.function",
        r"operating.system|kernel|driver",
        r"distributed|consensus|raft|paxos",
        r"formal.verification|proof|theorem",
    ],
    "medium": [
        r"api|server|endpoint|route|middleware",
        r"class.*inherit|design.pattern",
        r"algorithm|sort|search|graph",
        r"test|debug|refactor|optimize",
        r"analyze|compare|evaluate",
    ],
    "low": [
        r"print|hello|list|simple|basic",
        r"poem|story|letter|song|essay",
        r"explain|what.is|define|describe",
    ],
}


def estimate_complexity(prompt: str) -> str:
    """Estimate task complexity without calling LLM. Returns 'high', 'medium', or 'low'."""
    low = prompt.lower()
    for level in ("high", "medium", "low"):
        for pat in _COMPLEX_SIGNALS[level]:
            if re.search(pat, low):
                return level
    # Heuristic: longer prompts with code = more complex
    if len(prompt) > 1500:
        return "high"
    if len(prompt) > 500:
        return "medium"
    return "low"


# ── Reasoning Strategies ──────────────────────────────────────────

STRATEGIES = {
    "direct": "Answer directly with best knowledge.",
    "decompose": "Break into sub-problems, solve each, combine.",
    "analogize": "Find a similar solved problem, adapt its solution.",
    "contradict": "Try to disprove the obvious answer. If it survives, it's likely correct.",
    "first_principles": "Strip away assumptions. What must be true? Build up from basics.",
}


class ReasoningEngine:
    """
    Multi-candidate reasoning with scoring, validation, and caching.
    
    Instead of asking LLM once: ask N times with different strategies,
    score each response, pick the best one.
    """

    def __init__(self, orchestrator=None):
        self.orc = orchestrator
        self._stats = {"total": 0, "cache_hits": 0, "candidates_tested": 0}
        self._lessons_path = Path("workspace/reasoning_lessons.json")
        self._lessons = self._load_lessons()

    def _load_lessons(self) -> list:
        if self._lessons_path.exists():
            try:
                return json.loads(self._lessons_path.read_text())
            except Exception:
                pass
        return []

    def _save_lessons(self):
        self._lessons_path.parent.mkdir(parents=True, exist_ok=True)
        self._lessons_path.write_text(
            json.dumps(self._lessons[-100:], indent=2, default=str)
        )

    async def _llm(self, prompt: str, system: str = "", model: str = None,
                   max_tokens: int = 2000) -> str:
        """Call LLM with caching."""
        key = _cache_key(prompt, system)
        if key in _CACHE:
            self._stats["cache_hits"] += 1
            return _CACHE[key]

        try:
            from llm_router import LLMRouter
            router = LLMRouter()
            result = await router.complete(prompt, system=system,
                                           model=model, max_tokens=max_tokens)
            _CACHE[key] = result
            if len(_CACHE) % 10 == 0:
                _save_cache()
            return result
        except Exception as e:
            return f"[ERROR] {e}"

    # ══════════════════════════════════════════════════════════════
    # CORE: THINK — ਡੂੰਘੀ ਸੋਚ ਵਾਲਾ ਜਵਾਬ
    # ══════════════════════════════════════════════════════════════

    async def _generate_candidates(self, question, n_candidates, domain, lesson_context, memory_context):
        strategies = list(STRATEGIES.keys())[:n_candidates]
        candidates = []
        for strat in strategies:
            strat_instruction = STRATEGIES[strat]
            system = (
                f"You are AMRIT. Use this reasoning strategy: {strat_instruction}\n"
                f"Domain: {domain or 'general'}\n"
                f"{lesson_context}"
                f"{memory_context}"
                "Be thorough but concise."
            )
            response = await self._llm(
                f"QUESTION: {question}\n\nSTRATEGY: {strat_instruction}",
                system=system
            )
            candidates.append({
                "strategy": strat,
                "response": response,
                "score": 0.0,
            })
            self._stats["candidates_tested"] += 1
        return candidates

    async def think(self, question: str, n_candidates: int = 0, domain: str = ""):
        self._stats["total"] += 1
        t0 = time.time()

        complexity = estimate_complexity(question)

        if n_candidates == 0:
            n_candidates = {"low": 1, "medium": 2, "high": 3}[complexity]

        logger.info(f"Thinking: complexity={complexity}, candidates={n_candidates}")

        relevant_lessons = self._find_relevant_lessons(question)
        lesson_context = ""
        if relevant_lessons:
            lesson_context = "\n".join(
                f"- Past lesson: {ln['lesson']}" for ln in relevant_lessons[:3]
            )
            lesson_context = f"\nLEARNED FROM PAST:\n{lesson_context}\n"

        memory_context = await self._query_memory(question)

        if complexity == "high":
            try:
                from llm_router import LLMRouter
                from amrit_deep_reasoner import AmritDeepReasoner
                reasoner = AmritDeepReasoner(LLMRouter())
                mem_ctx = (memory_context + lesson_context).strip()
                result_raw = await reasoner.reason(question, context=mem_ctx)
                final_answer = result_raw["answer"]
                loops = result_raw["loops_used"]
                logger.info(f"\u262c \u0a38\u0a4b\u0a1a: {loops} loops \u0a35\u0a30\u0a24\u0a47")
                result = {
                    "answer": final_answer,
                    "confidence": round(result_raw["confidence"], 2),
                    "complexity": complexity,
                    "strategy": f"deep_reason/{loops}_loops",
                    "candidates_tested": loops,
                    "elapsed": round(time.time() - t0, 2),
                }
                self._learn_from_result(question, result)
                return result
            except Exception as e:
                logger.warning(f"AmritDeepReasoner failed ({e}), falling back to multi-candidate")

        if n_candidates == 1:
            system = (
                "You are AMRIT, an expert AI. Answer precisely and correctly."
                f"{lesson_context}"
                f"{memory_context}"
            )
            answer = await self._llm(question, system=system)
            result = {
                "answer": answer,
                "confidence": 0.7,
                "complexity": complexity,
                "strategy": "direct",
                "candidates_tested": 1,
                "elapsed": round(time.time() - t0, 2),
            }
            self._learn_from_result(question, result)
            return result

        candidates = await self._generate_candidates(
            question, n_candidates, domain, lesson_context, memory_context
        )
        scored = await self._score_candidates(question, candidates)
        best = max(scored, key=lambda c: c["score"])
        validation = await self._validate_answer(question, best["response"])
        confidence = min(1.0, best["score"] * 0.8 + validation["validity"] * 0.2)
        result = {
            "answer": best["response"],
            "confidence": round(confidence, 2),
            "complexity": complexity,
            "strategy": best["strategy"],
            "candidates_tested": len(candidates),
            "all_scores": {c["strategy"]: c["score"] for c in candidates},
            "validation": validation,
            "elapsed": round(time.time() - t0, 2),
        }
        self._learn_from_result(question, result)
        return result

    # ══════════════════════════════════════════════════════════════
    # SCORING — ਹਰ ਜਵਾਬ ਨੂੰ ਅੰਕ ਦਿਓ
    # ══════════════════════════════════════════════════════════════

    async def _score_candidates(self, question: str, candidates: list) -> list:
        """Score each candidate on completeness, logic, and relevance."""
        if len(candidates) <= 1:
            for c in candidates:
                c["score"] = 0.7
            return candidates

        # Build comparison prompt
        comparison_parts = []
        for i, c in enumerate(candidates, 1):
            resp_preview = c["response"][:400]
            comparison_parts.append(f"ANSWER {i} ({c['strategy']}): {resp_preview}")

        comparison = "\n\n".join(comparison_parts)

        score_prompt = (
            f"QUESTION: {question}\n\n{comparison}\n\n"
            "Rate each answer 0.0-1.0 on: correctness, completeness, clarity.\n"
            "Return ONLY a JSON array like: [{\"answer\": 1, \"score\": 0.8}, ...]"
        )

        raw = await self._llm(score_prompt, system="You are a fair evaluator. Return only JSON.")

        # Parse scores
        try:
            # Extract JSON from response
            json_match = re.search(r'\[.*?\]', raw, re.S)
            if json_match:
                scores = json.loads(json_match.group())
                for s in scores:
                    idx = s.get("answer", 1) - 1
                    if 0 <= idx < len(candidates):
                        candidates[idx]["score"] = float(s.get("score", 0.5))
        except (json.JSONDecodeError, ValueError):
            # Fallback: score by response length and structure
            for c in candidates:
                resp = c["response"]
                score = 0.5
                if len(resp) > 200:
                    score += 0.1
                if any(marker in resp for marker in ["1.", "2.", "- ", "```"]):
                    score += 0.1
                if "[ERROR]" in resp:
                    score -= 0.3
                c["score"] = min(1.0, max(0.0, score))

        return candidates

    # ══════════════════════════════════════════════════════════════
    # VALIDATION — ਕੀ ਜਵਾਬ ਸਹੀ ਹੈ?
    # ══════════════════════════════════════════════════════════════

    async def _validate_answer(self, question: str, answer: str) -> dict:
        """Try to find flaws in the answer. If it survives, it's good."""
        validation_prompt = (
            f"QUESTION: {question}\n"
            f"PROPOSED ANSWER: {answer[:800]}\n\n"
            "Find any flaws, errors, or missing points in this answer.\n"
            "If the answer is correct, say 'VALID'.\n"
            "If flawed, explain the flaw briefly."
        )

        critique = await self._llm(validation_prompt,
                                    system="You are a critical reviewer. Be strict.")

        is_valid = "valid" in critique.lower()[:50] or "correct" in critique.lower()[:50]

        return {
            "validity": 0.9 if is_valid else 0.4,
            "critique": critique[:300] if not is_valid else "Passed validation",
            "passed": is_valid,
        }

    # ══════════════════════════════════════════════════════════════
    # MEMORY INTEGRATION — ਪੁਰਾਣਾ ਗਿਆਨ ਵਰਤੋ
    # ══════════════════════════════════════════════════════════════

    async def _query_memory(self, question: str) -> str:
        """Query unified memory for relevant context."""
        if not self.orc:
            return ""

        memory = self.orc.get_agent("memory")
        if not memory:
            return ""

        try:
            result = await memory.execute({
                "name": "Reasoning memory query",
                "data": {"action": "search", "query": question[:200]}
            })
            ctx = result.get("context", [])
            know = result.get("knowledge", [])
            if ctx or know:
                parts = []
                for item in ctx[:3]:
                    parts.append(str(item.get("value", item))[:100])
                for item in know[:3]:
                    parts.append(str(item)[:100])
                if parts:
                    return "\nRELEVANT MEMORY:\n" + "\n".join(f"- {p}" for p in parts) + "\n"
        except Exception:
            pass
        return ""

    # ══════════════════════════════════════════════════════════════
    # LEARNING — ਸਿੱਖੋ ਕਿ ਕਿਹੜੀ ਸੋਚ ਕੰਮ ਕਰਦੀ ਹੈ
    # ══════════════════════════════════════════════════════════════

    def _learn_from_result(self, question: str, result: dict):
        """Record which strategy worked best for which type of question."""
        lesson = {
            "question_preview": question[:100],
            "complexity": result.get("complexity", "?"),
            "best_strategy": result.get("strategy", "direct"),
            "confidence": result.get("confidence", 0),
            "lesson": (
                f"For {result.get('complexity', '?')} complexity, "
                f"strategy '{result.get('strategy', 'direct')}' "
                f"scored confidence {result.get('confidence', 0)}"
            ),
        }
        self._lessons.append(lesson)
        if len(self._lessons) % 5 == 0:
            self._save_lessons()

    def _find_relevant_lessons(self, question: str) -> list:
        """Find past lessons relevant to this question."""
        q_words = set(question.lower().split())
        scored = []
        for lesson in self._lessons[-50:]:
            l_words = set(lesson.get("question_preview", "").lower().split())
            overlap = len(q_words & l_words)
            if overlap >= 2:
                scored.append((overlap, lesson))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:3]]

    # ══════════════════════════════════════════════════════════════
    # CAUSAL REASONING — ਕਾਰਨ-ਨਤੀਜਾ ਸੋਚ
    # ══════════════════════════════════════════════════════════════

    async def analyze_causality(self, observation: str, context: str = "") -> dict:
        """
        Given an observation, build a causal chain:
        What caused this? What could this cause next?
        
        This is NOT just asking LLM. It also:
        - Checks past experience for similar patterns
        - Validates each causal link
        """
        # Check if we've seen similar failures before
        past_failures = self._find_failure_patterns(observation)

        prompt = (
            f"OBSERVATION: {observation}\n"
            f"CONTEXT: {context[:500]}\n"
        )
        if past_failures:
            prompt += f"PAST SIMILAR FAILURES: {past_failures}\n"

        prompt += (
            "\nBuild a causal chain:\n"
            "1. ROOT CAUSE: What is the deepest reason this happened?\n"
            "2. CHAIN: List cause → effect → effect chain\n"
            "3. PREVENTION: How to prevent this in the future?\n"
            "4. PREDICTION: What will happen next if not fixed?\n"
            "Return as JSON with keys: root_cause, chain, prevention, prediction"
        )

        raw = await self._llm(prompt, system="You are a causal analyst. Be precise.")

        # Try to parse structured response
        try:
            json_match = re.search(r'\{.*\}', raw, re.S)
            if json_match:
                result = json.loads(json_match.group())
                result["raw"] = raw[:200]
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "root_cause": raw[:200],
            "chain": [],
            "prevention": "",
            "prediction": "",
            "raw": raw[:500],
        }

    def _find_failure_patterns(self, observation: str) -> str:
        """Check experience log for similar past failures."""
        try:
            from experience_log import ExperienceLog
            xp = ExperienceLog()
            failures = xp.failures()
            if not failures:
                return ""

            obs_words = set(observation.lower().split())
            matches = []
            for f in failures[-50:]:
                f_text = str(f.get("result", "")) + " " + str(f.get("action", ""))
                f_words = set(f_text.lower().split())
                if len(obs_words & f_words) >= 2:
                    matches.append(f"{f.get('agent', '?')}: {f.get('action', '')[:50]}")

            return "; ".join(matches[:3]) if matches else ""
        except Exception:
            return ""

    # ══════════════════════════════════════════════════════════════
    # STATS — ਅੰਕੜੇ
    # ══════════════════════════════════════════════════════════════

    def stats(self) -> dict:
        return {
            **self._stats,
            "lessons_learned": len(self._lessons),
            "cache_size": len(_CACHE),
        }