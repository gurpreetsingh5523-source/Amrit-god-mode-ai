"""Visual Memory — Stores and retrieves visual observations."""
from datetime import datetime

class VisualMemory:
    def __init__(self): self._obs=[]

    def store(self, desc: str, source: str, metadata=None):
        self._obs.append({"description":desc,"source":source,
                          "metadata":metadata or {},"ts":datetime.now().isoformat()})

    def recall_all(self) -> list: return list(self._obs)
    def search(self, q: str) -> list:
        return [o for o in self._obs if q.lower() in o["description"].lower()]
    def recent(self, n=5) -> list: return self._obs[-n:]
    def clear(self): self._obs.clear()
