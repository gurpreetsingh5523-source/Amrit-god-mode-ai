"""Planning Memory — Stores past plans for reuse."""
import json
from pathlib import Path
from datetime import datetime

class PlanningMemory:
    def __init__(self, path="workspace/plans.json"):
        self._path = Path(path)
        self._plans = []
        if self._path.exists():
            try:
                self._plans = json.loads(self._path.read_text())
            except Exception:
                pass

    def store(self, goal: str, tasks: list, result: str = ""):
        self._plans.append({"goal":goal,"tasks":tasks,"result":result,
                             "time":datetime.now().isoformat()})
        if len(self._plans) > 200:
            self._plans = self._plans[-200:]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._plans, indent=2))

    def find_similar(self, goal: str) -> list:
        g = goal.lower()
        return [p for p in self._plans if any(w in p["goal"].lower() for w in g.split())][:3]

    def stats(self) -> dict:
        return {"total_plans": len(self._plans)}
