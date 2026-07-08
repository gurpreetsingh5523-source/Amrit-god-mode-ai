"""Context Buffer — Short-term rolling memory."""
from collections import deque
from datetime import datetime

class ContextBuffer:
    def __init__(self, max_size=40):
        self._buf = deque(maxlen=max_size)
        self.max_size = max_size

    def add(self, entry: dict):
        entry.setdefault("timestamp", datetime.now().isoformat())
        self._buf.append(entry)

    def add_message(self, role: str, content: str, agent: str = ""):
        self.add({"role":role,"content":content,"agent":agent})

    def get_all(self) -> list: return list(self._buf)
    def get_last(self, n=5) -> list: return list(self._buf)[-n:]
    def to_messages(self) -> list:
        return [{"role":e.get("role","user"),"content":e.get("content","")} for e in self._buf]
    def clear(self): self._buf.clear()
    def __len__(self): return len(self._buf)
