"""Experience Log — Agent action history for self-learning."""
import json
from datetime import datetime
from pathlib import Path

class ExperienceLog:
    def __init__(self, path="workspace/experience.json"):
        self._log = []
        self._path = Path(path)
        if self._path.exists():
            try:
                self._log = json.loads(self._path.read_text())
            except Exception:
                pass

    def record(self, agent: str, action: str, result: dict, task="", success=True):
        self._log.append({"agent":agent,"action":action,"task":task,"result":result,
                          "success":success,"timestamp":datetime.now().isoformat()})
        if len(self._log) % 10 == 0:
            self.save()

    def get_all(self) -> list: return list(self._log)
    def by_agent(self, agent: str) -> list: return [e for e in self._log if e["agent"]==agent]
    def failures(self) -> list: return [e for e in self._log if not e.get("success",True)]
    def recent(self, n=20) -> list: return self._log[-n:]
    def stats(self) -> dict:
        total = len(self._log)
        succ = sum(1 for e in self._log if e.get("success",True))
        return {"total":total,"success":succ,"failed":total-succ,"rate":round(succ/total,2) if total else 0}

    def save(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._path.write_text(json.dumps(self._log,indent=2,default=str))
