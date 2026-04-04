"""
Learning Layer — ਸਿੱਖਣ ਦੀ ਪਰਤ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AMRIT ਦਾ self-correction ਅਤੇ evolution DNA

ਚੱਕਰ (Feedback Cycle):
  1. ਦੇਖ (Observe)   — ਗਲਤੀ ਜਾਂ ਕਮਜ਼ੋਰੀ ਫੜੋ
  2. ਸੋਚ (Reflect)   — ਕਾਰਨ ਲੱਭੋ, ਪੈਟਰਨ ਸਮਝੋ
  3. ਠੀਕ (Correct)   — ਲਾਜ਼ਿਕ ਬਦਲੋ, ਸੁਧਾਰ ਕਰੋ
  4. ਯਾਦ (Record)    — ਸਬਕ ਸੇਵ ਕਰੋ ਤਾਂ ਜੋ ਦੁਬਾਰਾ ਨਾ ਹੋਵੇ

ੴ ਸਤਿਨਾਮ — ਹਰ ਗਲਤੀ ਇੱਕ ਸਿੱਖਿਆ ਹੈ।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
from datetime import datetime
from pathlib import Path
from collections import Counter
from logger import setup_logger

logger = setup_logger("LearningLayer")

LESSONS_PATH = Path("workspace/learning_lessons.json")
PATTERNS_PATH = Path("workspace/failure_patterns.json")


class LearningLayer:
    """
    ਸਿੱਖਣ ਦੀ ਪਰਤ — observe → reflect → correct → record

    ਇਹ ਸਾਰੇ ਸਿਸਟਮ ਦੇ ਤਜਰਬੇ ਇਕੱਠੇ ਕਰਦੀ ਹੈ,
    ਪੈਟਰਨ ਲੱਭਦੀ ਹੈ, ਅਤੇ ਸਬਕ ਬਣਾਉਂਦੀ ਹੈ।
    """

    def __init__(self):
        self._lessons = self._load(LESSONS_PATH, default=[])
        self._patterns = self._load(PATTERNS_PATH, default=[])

    # ──────────────────────────────────────────────
    # 1. ਦੇਖ (Observe) — ਕੀ ਗਲਤ ਹੋਇਆ?
    # ──────────────────────────────────────────────
    def observe(self, event: dict) -> dict | None:
        """
        ਘਟਨਾ ਦੇਖੋ ਅਤੇ ਫ਼ੈਸਲਾ ਕਰੋ ਕਿ ਇਹ ਸਬਕ ਬਣਦੀ ਹੈ ਕਿ ਨਹੀਂ।

        event ਵਿੱਚ ਇਹ ਹੋਣੇ ਚਾਹੀਦੇ:
            agent  — ਕਿਹੜੇ agent ਨੇ ਕੰਮ ਕੀਤਾ
            action — ਕੀ ਕੀਤਾ
            success — ਕਾਮਯਾਬ ਹੋਇਆ ਜਾਂ ਨਹੀਂ
            error  — (ਜੇ ਫੇਲ੍ਹ) ਕੀ ਗਲਤੀ ਸੀ
        """
        if event.get("success", True):
            return None  # ਕਾਮਯਾਬੀ — ਸਿੱਖਣ ਦੀ ਲੋੜ ਨਹੀਂ

        agent = event.get("agent", "unknown")
        action = event.get("action", "unknown")
        error = event.get("error", "")

        # ਕੀ ਇਹ ਪਹਿਲਾਂ ਵੀ ਹੋ ਚੁੱਕੀ ਹੈ?
        pattern = self._find_pattern(agent, error)
        if pattern:
            pattern["count"] = pattern.get("count", 1) + 1
            pattern["last_seen"] = datetime.now().isoformat()
            logger.info(f"  🔁 ਪੁਰਾਣੀ ਗਲਤੀ ({pattern['count']}ਵੀਂ ਵਾਰ): {agent}/{action}")
        else:
            pattern = {
                "agent": agent,
                "action": action,
                "error_key": error[:100].lower().strip(),
                "count": 1,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "fix": None,
            }
            self._patterns.append(pattern)
            logger.info(f"  🆕 ਨਵੀਂ ਗਲਤੀ ਫੜੀ: {agent}/{action}")

        self._save(PATTERNS_PATH, self._patterns)
        return pattern

    # ──────────────────────────────────────────────
    # 2. ਸੋਚ (Reflect) — ਕਿਉਂ ਹੋਇਆ?
    # ──────────────────────────────────────────────
    def reflect(self) -> list:
        """
        ਸਾਰੇ ਪੈਟਰਨਾਂ ਉੱਤੇ ਸੋਚੋ — ਕਿਹੜੇ agent ਸਭ ਤੋਂ ਵੱਧ ਫੇਲ੍ਹ?
        ਕਿਹੜੀ ਗਲਤੀ ਵਾਰ-ਵਾਰ ਆਉਂਦੀ?
        """
        if not self._patterns:
            return []

        # ਸਭ ਤੋਂ ਵੱਧ ਫੇਲ੍ਹ ਹੋਣ ਵਾਲੇ agent
        agent_counts = Counter(p["agent"] for p in self._patterns)
        # ਵਾਰ-ਵਾਰ ਆਉਣ ਵਾਲੀਆਂ ਗਲਤੀਆਂ (3+ ਵਾਰ)
        recurring = [p for p in self._patterns if p.get("count", 1) >= 3]

        insights = []
        for agent, cnt in agent_counts.most_common(3):
            insights.append({
                "type": "ਕਮਜ਼ੋਰ_agent",
                "agent": agent,
                "failure_count": cnt,
                "advice": f"{agent} ਨੂੰ ਵਧੇਰੇ ਧਿਆਨ ਚਾਹੀਦਾ — {cnt} ਵਾਰ ਫੇਲ੍ਹ"
            })
        for p in recurring:
            insights.append({
                "type": "ਵਾਰ-ਵਾਰ_ਗਲਤੀ",
                "agent": p["agent"],
                "error": p["error_key"][:60],
                "count": p["count"],
                "advice": f"ਇਹ ਗਲਤੀ {p['count']} ਵਾਰ ਹੋਈ — ਪੱਕਾ ਹੱਲ ਚਾਹੀਦਾ"
            })

        if insights:
            logger.info(f"  🪞 ਸੋਚ (Reflect): {len(insights)} ਸਬਕ ਮਿਲੇ")
        return insights

    # ──────────────────────────────────────────────
    # 3. ਠੀਕ (Correct) — ਸੁਧਾਰ ਲਾਗੂ ਕਰੋ
    # ──────────────────────────────────────────────
    def correct(self, pattern: dict, fix_description: str):
        """
        ਜਦੋਂ ਕੋਈ ਗਲਤੀ ਠੀਕ ਹੋ ਜਾਵੇ, ਇੱਥੇ ਦੱਸੋ ਕਿ ਕਿਵੇਂ ਠੀਕ ਹੋਈ।
        ਅਗਲੀ ਵਾਰ ਇਹੀ ਹੱਲ ਆਪੇ ਲੱਭੇਗਾ।
        """
        # ਪੈਟਰਨ ਵਿੱਚ fix ਸੇਵ ਕਰੋ
        for p in self._patterns:
            if p.get("error_key") == pattern.get("error_key") and p.get("agent") == pattern.get("agent"):
                p["fix"] = fix_description
                p["fixed_at"] = datetime.now().isoformat()
                break

        self._save(PATTERNS_PATH, self._patterns)
        logger.info(f"  ✅ ਸੁਧਾਰ ਸੇਵ ਕੀਤਾ: {pattern.get('agent')}/{pattern.get('error_key','')[:40]}")

    # ──────────────────────────────────────────────
    # 4. ਯਾਦ (Record) — ਸਬਕ ਲਿਖੋ
    # ──────────────────────────────────────────────
    def record_lesson(self, lesson: str, source: str = "auto", tags: list = None):
        """
        ਸਬਕ ਸੇਵ ਕਰੋ — ਭਵਿੱਖ ਲਈ ਯਾਦ ਰੱਖਣਾ।
        """
        entry = {
            "lesson": lesson,
            "source": source,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
        }
        self._lessons.append(entry)
        # ਵੱਧ ਤੋਂ ਵੱਧ 200 ਸਬਕ ਰੱਖੋ
        if len(self._lessons) > 200:
            self._lessons = self._lessons[-200:]
        self._save(LESSONS_PATH, self._lessons)
        logger.info(f"  📝 ਸਬਕ ਸੇਵ ਕੀਤਾ: {lesson[:60]}")

    # ──────────────────────────────────────────────
    # ਪੁਰਾਣੇ ਸਬਕ ਲੱਭੋ — ਕੀ ਪਹਿਲਾਂ ਇਹ ਗਲਤੀ ਹੋਈ ਸੀ?
    # ──────────────────────────────────────────────
    def find_known_fix(self, agent: str, error: str) -> str | None:
        """
        ਜੇ ਇਹ ਗਲਤੀ ਪਹਿਲਾਂ ਹੋਈ ਸੀ ਅਤੇ ਉਸ ਦਾ ਹੱਲ ਪਤਾ ਹੈ,
        ਤਾਂ ਹੱਲ ਵਾਪਸ ਦਿਓ। ਨਹੀਂ ਤਾਂ None।
        """
        pattern = self._find_pattern(agent, error)
        if pattern and pattern.get("fix"):
            logger.info(f"  💡 ਪੁਰਾਣਾ ਹੱਲ ਮਿਲਿਆ: {pattern['fix'][:50]}")
            return pattern["fix"]
        return None

    def get_lessons(self, tag: str = None, n: int = 20) -> list:
        """ਤਾਜ਼ਾ ਸਬਕ ਦਿਓ, tag ਨਾਲ ਫਿਲਟਰ ਕਰ ਸਕਦੇ ਹੋ।"""
        if tag:
            filtered = [l for l in self._lessons if tag in l.get("tags", [])]
            return filtered[-n:]
        return self._lessons[-n:]

    def stats(self) -> dict:
        """ਸੰਖੇਪ ਅੰਕੜੇ।"""
        total_patterns = len(self._patterns)
        fixed = sum(1 for p in self._patterns if p.get("fix"))
        recurring = sum(1 for p in self._patterns if p.get("count", 1) >= 3)
        return {
            "total_lessons": len(self._lessons),
            "total_error_patterns": total_patterns,
            "patterns_with_fix": fixed,
            "recurring_errors": recurring,
        }

    # ── ਅੰਦਰੂਨੀ ਸਹਾਇਕ ────────────────────────
    def _find_pattern(self, agent: str, error: str) -> dict | None:
        key = error[:100].lower().strip()
        for p in self._patterns:
            if p.get("agent") == agent and p.get("error_key") == key:
                return p
        return None

    @staticmethod
    def _load(path: Path, default=None):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return default if default is not None else []

    @staticmethod
    def _save(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
