"""
skill_crystallizer.py — Skill Crystallization (token-saving replay)
═══════════════════════════════════════════════════════════════════
When a multi-agent/swarm task SUCCEEDS, extract its execution PATH
(which agents + actions, in what order) into a reusable "skill".
Next time a SIMILAR goal arrives, match it semantically and REPLAY
the stored path — skipping the expensive LLM planning step.

This is the GenericAgent/Evolver "crystallization" idea, adapted for
Amrit. Real saving: a repeat task skips planner decomposition (1-3
DeepSeek calls) and runs the known-good path directly.

    from skill_crystallizer import SkillCrystallizer
    sc = SkillCrystallizer()
    skill = sc.find_match("build a fastapi dashboard")   # None or skill dict
    sc.crystallize(objective, tasks, success=True)        # save on success
    sc.record_usage(skill_id, success=True, tokens_saved=1200)
"""

import json
import re
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("SkillCrystallizer")

SKILLS_DIR = Path("workspace/skills")
MATCH_THRESHOLD = 0.88   # HIGH bar — only replay near-identical goals
                         # (loose matching replays the wrong path; see expense-vs-dashboard bug)


class SkillCrystallizer:
    def __init__(self, match_threshold: float = MATCH_THRESHOLD):
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        self.threshold = match_threshold
        self._embedder = None
        self._skills = self._load_all()

    # ── persistence ──────────────────────────────────────────────
    def _load_all(self) -> list:
        skills = []
        for f in SKILLS_DIR.glob("*.json"):
            try:
                skills.append(json.loads(f.read_text()))
            except Exception:
                pass
        return skills

    def _save(self, skill: dict):
        path = SKILLS_DIR / f"{skill['skill_id']}.json"
        path.write_text(json.dumps(skill, indent=2, default=str))

    # ── embedding (lazy, reuse Amrit's model; fallback to keywords) ──
    def _embedder_model(self):
        if self._embedder is None:
            try:
                from embedding_model import EmbeddingModel
                self._embedder = EmbeddingModel()
            except Exception:
                self._embedder = False
        return self._embedder or None

    def _similar(self, a: str, b: str) -> float:
        m = self._embedder_model()
        if m:
            try:
                return float(m.similarity(a, b))
            except Exception:
                pass
        # fallback: token Jaccard overlap
        sa = set(re.findall(r"[a-z0-9]+", a.lower()))
        sb = set(re.findall(r"[a-z0-9]+", b.lower()))
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    @staticmethod
    def _skill_id(objective: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", objective.lower()).strip("_")[:40]
        return slug or "skill"

    # ── crystallize a successful task into a reusable skill ──────────
    def crystallize(self, objective: str, tasks: list, success: bool = True) -> dict | None:
        """Save the execution path of a successful task as a skill."""
        if not success or not tasks:
            return None

        # Extract the path: ordered (agent, action) steps
        path = []
        for t in tasks:
            agent = t.get("agent") or t.get("agent_name") or "coder"
            data = t.get("data", {})
            path.append({
                "agent": agent,
                "action": data.get("action", "generate"),
                "name": t.get("name", "")[:120],
            })
        if not path:
            return None

        sid = self._skill_id(objective)
        # If a near-identical skill exists, bump its stats instead of duplicating
        for s in self._skills:
            if s["skill_id"] == sid or self._similar(s["task_pattern"], objective) > 0.9:
                s["usage_count"] = s.get("usage_count", 0) + 1
                self._save(s)
                logger.info(f"  💎 Reinforced skill '{s['skill_id']}' (uses={s['usage_count']})")
                return s

        skill = {
            "skill_id": sid,
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "task_pattern": objective[:300],
            "execution_path": path,
            "steps": len(path),
            "usage_count": 0,
            "success_rate": 1.0,
            "tokens_saved": 0,
        }
        self._skills.append(skill)
        self._save(skill)
        logger.info(f"  💎 Crystallized NEW skill '{sid}' ({len(path)} steps)")
        return skill

    # ── find a matching skill for a new goal ────────────────────────
    def find_match(self, objective: str) -> dict | None:
        """Return the best-matching skill above threshold, SKIPPING skills that
        have proven unreliable (used before but low success_rate)."""
        best, best_score = None, 0.0
        for s in self._skills:
            # auto-prune from replay: if it's been tried and fails often, don't trust it
            if s.get("usage_count", 0) >= 2 and s.get("success_rate", 1.0) < 0.5:
                continue
            score = self._similar(s["task_pattern"], objective)
            if score > best_score:
                best, best_score = s, score
        if best and best_score >= self.threshold:
            logger.info(f"  ⚡ Skill match: '{best['skill_id']}' (similarity {best_score:.2f}, "
                        f"rate {best.get('success_rate',1.0):.2f}) → replay {best['steps']} steps")
            return best
        return None

    def prune(self) -> int:
        """Delete skills that have proven consistently bad (used ≥3×, rate <0.34)."""
        keep, removed = [], 0
        for s in self._skills:
            if s.get("usage_count", 0) >= 3 and s.get("success_rate", 1.0) < 0.34:
                p = SKILLS_DIR / f"{s['skill_id']}.json"
                p.unlink(missing_ok=True)
                removed += 1
            else:
                keep.append(s)
        self._skills = keep
        if removed:
            logger.info(f"  🗑 pruned {removed} consistently-failing skill(s)")
        return removed

    def record_usage(self, skill_id: str, success: bool, tokens_saved: int = 0):
        for s in self._skills:
            if s["skill_id"] == skill_id:
                s["usage_count"] = s.get("usage_count", 0) + 1
                # rolling success rate
                n = s["usage_count"]
                prev = s.get("success_rate", 1.0)
                s["success_rate"] = round((prev * (n - 1) + (1.0 if success else 0.0)) / n, 3)
                s["tokens_saved"] = s.get("tokens_saved", 0) + tokens_saved
                self._save(s)
                return

    def replay_tasks(self, skill: dict, objective: str) -> list:
        """Turn a stored skill path into a fresh task list for the swarm."""
        tasks = []
        for step in skill["execution_path"]:
            # Reuse the STRUCTURE (agent + action sequence) but feed the NEW goal
            # as the spec so the step builds the CURRENT task, not the old one.
            tasks.append({
                "name": f"{step.get('name','step')} (for: {objective[:50]})",
                "agent": step["agent"],
                "priority": 1,
                "data": {"action": step.get("action", "generate"),
                         "spec": objective, "goal": objective},
                "depends_on": [],
            })
        return tasks

    def status(self) -> dict:
        return {
            "total_skills": len(self._skills),
            "total_uses": sum(s.get("usage_count", 0) for s in self._skills),
            "total_tokens_saved": sum(s.get("tokens_saved", 0) for s in self._skills),
            "skills": [{"id": s["skill_id"], "uses": s.get("usage_count", 0),
                        "rate": s.get("success_rate", 1.0)} for s in self._skills],
        }


# ── self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 55)
    print("💎 SkillCrystallizer — Self Test")
    print("═" * 55)
    import shutil
    if SKILLS_DIR.exists():
        shutil.rmtree(SKILLS_DIR)
    sc = SkillCrystallizer()

    # 1. crystallize a successful task
    tasks = [
        {"name": "Generate app.py FastAPI /stats", "agent": "coder", "data": {"action": "generate"}},
        {"name": "Generate index.html dashboard", "agent": "coder", "data": {"action": "generate"}},
        {"name": "Test endpoint", "agent": "tester", "data": {"action": "run"}},
    ]
    sc.crystallize("build a fastapi analytics dashboard with stats endpoint", tasks, success=True)

    # 2. a SIMILAR new goal should match
    m = sc.find_match("build a fastapi dashboard showing analytics stats")
    print(f"\n  Similar goal → match: {'✅ '+m['skill_id'] if m else '❌ none'}")

    # 3. an UNRELATED goal should NOT match
    m2 = sc.find_match("translate this document to Punjabi")
    print(f"  Unrelated goal → match: {'❌ wrongly matched '+m2['skill_id'] if m2 else '✅ correctly no match'}")

    # 4. replay
    if m:
        replay = sc.replay_tasks(m, "build a fastapi dashboard")
        print(f"  Replay tasks: {len(replay)} steps ({[t['agent'] for t in replay]})")
        sc.record_usage(m["skill_id"], success=True, tokens_saved=1500)

    print(f"\n  Status: {sc.status()}")
    ok = m is not None and m2 is None
    print(f"\n  {'🏆 SKILL CRYSTALLIZATION WORKS' if ok else '⚠️ check matching'}")
