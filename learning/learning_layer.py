"""
Learning Layer — ਸਿੱਖਣ ਦਾ ਦਿਮਾਗ (LLM-Independent)
═══════════════════════════════════════════════════════
ਇਹ ਸਿਸਟਮ LLM ਤੋਂ ਬਿਨਾਂ ਸਿੱਖਦਾ ਹੈ:
  1. ਦੇਖ (Observe) — ਕੀ ਗਲਤ ਹੋਇਆ?
  2. ਪੈਟਰਨ (Pattern) — ਕੀ ਇਹ ਪਹਿਲਾਂ ਵੀ ਹੋਇਆ?
  3. ਸਬਕ (Lesson) — ਕੀ ਸਿੱਖਿਆ?
  4. ਅਮਲ (Apply) — ਅਗਲੀ ਵਾਰ ਕੀ ਕਰੀਏ?
"""

import json
from collections import Counter
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("LearningLayer")

LESSONS_PATH = Path("workspace/learning_lessons.json")
PATTERNS_PATH = Path("workspace/learning_patterns.json")


class LearningLayer:
    def __init__(self):
        self._lessons = self._load(LESSONS_PATH, [])
        self._patterns = self._load(PATTERNS_PATH, [])
        self._failure_counts = Counter()  # agent → fail count
        self._success_counts = Counter()  # agent → success count
        self._error_patterns = Counter()  # error_type → count
        self._agent_skills = {}  # agent → {skill: score}

    # ══════════════════════════════════════════════════════════════
    # 1. ਦੇਖ (Observe) — Experience ਤੋਂ ਸਿੱਖੋ
    # ══════════════════════════════════════════════════════════════

    def observe(
        self,
        agent_or_dict,
        action: str = None,
        success: bool = None,
        error: str = "",
        duration: float = 0,
        context: dict = None,
    ):
        """ਹਰ task ਦੇ ਬਾਅਦ observe ਕਰੋ — ਕੀ ਹੋਇਆ?
        
        Dict ਜਾਂ positional args ਦੋਵੇਂ ਤਰੀਕੇ ਕੰਮ ਕਰਦੇ ਹਨ:
          ll.observe({"agent": "x", "action": "y", "success": True})
          ll.observe("agent", "action", True)
        """
        if isinstance(agent_or_dict, dict):
            d = agent_or_dict
            agent = d.get("agent", "unknown")
            action = d.get("action", "unknown")
            success = bool(d.get("success", False))
            error = d.get("error", "")
            duration = d.get("duration", 0)  # noqa: F841
            context = d.get("context")  # noqa: F841
        else:
            agent = agent_or_dict
        if success:
            self._success_counts[agent] += 1
            self._update_skill(agent, action, +0.1)
        else:
            self._failure_counts[agent] += 1
            self._update_skill(agent, action, -0.2)
            error_type = self._classify_error(error)
            self._error_patterns[error_type] += 1
            self._detect_pattern(agent, action, error_type, error)

        # ਹਰ 20 observations ਤੇ save ਕਰੋ
        total = sum(self._success_counts.values()) + sum(self._failure_counts.values())
        if total % 20 == 0:
            self._save_all()

    # ══════════════════════════════════════════════════════════════
    # 2. ਪੈਟਰਨ (Pattern Detection) — ਕੀ ਵਾਰ ਵਾਰ ਹੋ ਰਿਹਾ?
    # ══════════════════════════════════════════════════════════════

    def _detect_pattern(self, agent: str, action: str, error_type: str, error: str):
        """ਜੇ ਇੱਕੋ ਗਲਤੀ 3+ ਵਾਰ ਹੋਵੇ → ਸਬਕ ਬਣਾਓ"""
        key = f"{agent}:{error_type}"
        count = self._error_patterns[error_type]

        if count >= 3 and not self._has_lesson(key):
            lesson = self._generate_lesson(agent, error_type, error, count)
            self._lessons.append(lesson)
            self._patterns.append(
                {
                    "key": key,
                    "agent": agent,
                    "error_type": error_type,
                    "count": count,
                    "detected": datetime.now().isoformat(),
                }
            )
            logger.info(f"🧠 ਨਵਾਂ ਸਬਕ: {lesson['lesson']}")

    def _generate_lesson(
        self, agent: str, error_type: str, error: str, count: int
    ) -> dict:
        """Rule-based lesson generation — ਕੋਈ LLM ਨਹੀਂ ਚਾਹੀਦਾ"""
        LESSON_RULES = {
            "timeout": {
                "lesson": f"Agent '{agent}' ਵਾਰ ਵਾਰ timeout ਹੁੰਦਾ → ਟਾਸਕ ਛੋਟਾ ਕਰੋ ਜਾਂ timeout ਵਧਾਓ",
                "action": "reduce_task_size",
                "priority": "high",
            },
            "import_error": {
                "lesson": f"Agent '{agent}' ਵਿੱਚ import ਗਲਤੀਆਂ → dependencies ਚੈੱਕ ਕਰੋ",
                "action": "check_dependencies",
                "priority": "critical",
            },
            "api_error": {
                "lesson": "API ਕਾਲਾਂ ਫੇਲ੍ਹ ਹੋ ਰਹੀਆਂ → ਲੋਕਲ ਮਾਡਲ ਵਰਤੋ",
                "action": "switch_to_local",
                "priority": "high",
            },
            "memory_error": {
                "lesson": "ਮੈਮੋਰੀ ਘੱਟ ਹੈ → batch size ਘਟਾਓ ਜਾਂ ਛੋਟਾ ਮਾਡਲ ਵਰਤੋ",
                "action": "reduce_batch_size",
                "priority": "critical",
            },
            "syntax_error": {
                "lesson": f"Agent '{agent}' ਵਿੱਚ syntax ਗਲਤੀਆਂ → code validation ਵਧਾਓ",
                "action": "add_validation",
                "priority": "medium",
            },
            "connection_error": {
                "lesson": "ਕਨੈਕਸ਼ਨ ਸਮੱਸਿਆ → retry ਨਾਲ backoff ਵਰਤੋ",
                "action": "add_retry",
                "priority": "medium",
            },
        }
        rule = LESSON_RULES.get(
            error_type,
            {
                "lesson": f"Agent '{agent}' ਵਿੱਚ '{error_type}' ਗਲਤੀ {count} ਵਾਰ → ਜਾਂਚ ਕਰੋ",
                "action": "investigate",
                "priority": "low",
            },
        )
        return {
            **rule,
            "agent": agent,
            "error_type": error_type,
            "occurrences": count,
            "created": datetime.now().isoformat(),
        }

    # ══════════════════════════════════════════════════════════════
    # 3. ਸਲਾਹ (Recommendations) — ਅਗਲੀ ਵਾਰ ਕੀ ਕਰੀਏ?
    # ══════════════════════════════════════════════════════════════

    def recommend_agent(self, task_type: str) -> str:
        """ਸਭ ਤੋਂ ਵਧੀਆ agent ਚੁਣੋ ਤਜ਼ਰਬੇ ਦੇ ਆਧਾਰ ਤੇ"""
        best_agent = None
        best_score = -999
        for agent, skills in self._agent_skills.items():
            for skill, score in skills.items():
                if task_type.lower() in skill.lower() and score > best_score:
                    best_score = score
                    best_agent = agent
        return best_agent or "planner"

    def get_lessons_for(self, agent: str = None, error_type: str = None) -> list:
        """ਕਿਸੇ agent ਜਾਂ error type ਲਈ ਸਬਕ ਲੱਭੋ"""
        results = self._lessons
        if agent:
            results = [lesson for lesson in results if lesson.get("agent") == agent]
        if error_type:
            results = [
                lesson for lesson in results if lesson.get("error_type") == error_type
            ]
        return results

    def get_action_for_error(self, error_type: str) -> str:
        """ਗਲਤੀ ਲਈ ਸਿੱਖਿਆ ਹੋਇਆ ਅਮਲ ਦੱਸੋ"""
        for lesson in reversed(self._lessons):
            if lesson.get("error_type") == error_type:
                return lesson.get("action", "investigate")
        return "investigate"

    def get_summary(self) -> dict:
        """ਸਿੱਖਣ ਦਾ ਸੰਖੇਪ"""
        return {
            "total_lessons": len(self._lessons),
            "total_patterns": len(self._patterns),
            "top_failures": dict(self._failure_counts.most_common(5)),
            "top_errors": dict(self._error_patterns.most_common(5)),
            "agent_scores": {
                a: round(sum(s.values()) / max(len(s), 1), 2)
                for a, s in self._agent_skills.items()
            },
        }

    def stats(self) -> dict:
        """get_summary() ਦਾ alias — backward compatibility"""
        return self.get_summary()

    # ══════════════════════════════════════════════════════════════
    # ਅੰਦਰੂਨੀ ਫੰਕਸ਼ਨ (Internal Helpers)
    # ══════════════════════════════════════════════════════════════

    def _classify_error(self, error: str) -> str:
        e = error.lower()
        if "timeout" in e:
            return "timeout"
        if "import" in e or "module" in e:
            return "import_error"
        if "api" in e or "http" in e or "404" in e:
            return "api_error"
        if "memory" in e or "oom" in e:
            return "memory_error"
        if "syntax" in e:
            return "syntax_error"
        if "connection" in e or "refused" in e:
            return "connection_error"
        if "permission" in e:
            return "permission_error"
        return "unknown"

    def _update_skill(self, agent: str, action: str, delta: float):
        self._agent_skills.setdefault(agent, {})
        skill = action.split()[0] if action else "general"
        current = self._agent_skills[agent].get(skill, 0.5)
        self._agent_skills[agent][skill] = max(0.0, min(1.0, current + delta))

    def _has_lesson(self, key: str) -> bool:
        return any(p.get("key") == key for p in self._patterns)

    def _save_all(self):
        LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LESSONS_PATH.write_text(json.dumps(self._lessons[-200:], indent=2, default=str))
        PATTERNS_PATH.write_text(
            json.dumps(self._patterns[-200:], indent=2, default=str)
        )

    @staticmethod
    def _load(path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return default
