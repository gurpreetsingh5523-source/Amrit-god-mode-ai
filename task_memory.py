"""
task_memory.py — cross-session TASK experience memory  [Roadmap Phase 2]
═══════════════════════════════════════════════════════════════════════════
Amrit already RECORDS episodes/failures, but never RECALLS its own past task
experience to inform a NEW task. This closes that loop: every code task's
outcome (success/fail + a short lesson) is saved, and before a new task the
most semantically-similar past experiences are recalled and fed to the coder —
so Amrit gets continuity ("last time I built X, Y worked / Z failed").

    from task_memory import TaskMemory
    tm = TaskMemory()
    tm.record(task, success=True, note="used new ForceGraph3D()(el) factory form")
    ctx = tm.recall_text(new_task)   # "" or a few relevant past lessons
"""
import json
import re
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("TaskMemory")
STORE = Path("workspace/task_memory.json")
SIM_THRESHOLD = 0.45   # looser than skill replay — we want hints, not exact reuse


class TaskMemory:
    def __init__(self):
        self._embedder = None
        self._items = self._load()

    def _load(self):
        try:
            return json.loads(STORE.read_text()) if STORE.exists() else []
        except Exception:
            return []

    def _save(self):
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(self._items[-500:], indent=1))  # cap history

    def _model(self):
        if self._embedder is None:
            try:
                from embedding_model import EmbeddingModel
                self._embedder = EmbeddingModel()
            except Exception:
                self._embedder = False
        return self._embedder or None

    def _sim(self, a, b):
        m = self._model()
        if m:
            try:
                return float(m.similarity(a, b))
            except Exception:
                pass
        sa, sb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
        return len(sa & sb) / len(sa | sb) if sa and sb else 0.0

    def record(self, task: str, success: bool, note: str = "") -> None:
        """Save a task outcome + short lesson."""
        if not task:
            return
        self._items.append({
            "task": task[:300], "success": bool(success), "note": (note or "")[:300],
            "ts": datetime.now().isoformat(),
        })
        self._save()

    def recall(self, task: str, k: int = 3) -> list:
        """Return up to k most-similar past experiences above threshold."""
        scored = [(self._sim(task, it["task"]), it) for it in self._items]
        scored = [(s, it) for s, it in scored if s >= SIM_THRESHOLD]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:k]]

    def recall_text(self, task: str, k: int = 3) -> str:
        """Formatted recall to inject into a generation prompt (or '')."""
        hits = self.recall(task, k)
        if not hits:
            return ""
        lines = []
        for h in hits:
            tag = "✅ worked" if h["success"] else "❌ failed"
            note = f" — {h['note']}" if h["note"] else ""
            lines.append(f"- ({tag}) {h['task'][:80]}{note}")
        return "\n".join(lines)

    def stats(self) -> dict:
        n = len(self._items)
        ok = sum(1 for i in self._items if i["success"])
        return {"total": n, "successes": ok, "failures": n - ok}


if __name__ == "__main__":
    STORE.unlink(missing_ok=True)
    tm = TaskMemory()
    tm.record("build a 3d-force-graph dashboard", True, "use ForceGraph3D()(el) factory form")
    tm.record("build a fastapi crud api", True, "in-memory list + TestClient verified")
    tm.record("translate a doc to punjabi", False, "no translator wired")
    print("═" * 50)
    print("🧠 TaskMemory self-test")
    print("  recall for 'make a 3d force graph page':")
    print("   ", tm.recall_text("make a 3d force graph page") or "(none)")
    print("  recall for 'cook dinner' (should be empty):")
    print("   ", tm.recall_text("cook dinner") or "(none)")
    print("  stats:", tm.stats())
    ok = bool(tm.recall("make a 3d force graph page")) and not tm.recall("cook dinner")
    print("\n  🏆 WORKS" if ok else "  ⚠️ check")
