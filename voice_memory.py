"""Voice Memory — Stores transcribed conversations."""
import json
from datetime import datetime
from pathlib import Path

class VoiceMemory:
    def __init__(self, path="workspace/voice_log.json"):
        self._log=[]; self._path=Path(path)
        if self._path.exists():
            try: self._log=json.loads(self._path.read_text())
            except: pass

    def record(self, role: str, text: str, emotion: str = "neutral"):
        entry={"role":role,"text":text,"emotion":emotion,"ts":datetime.now().isoformat()}
        self._log.append(entry); self.save()

    def recent(self, n=20) -> list: return self._log[-n:]
    def search(self, q: str) -> list:
        return [e for e in self._log if q.lower() in e["text"].lower()]
    def to_context(self, n=10) -> list:
        return [{"role":e["role"],"content":e["text"]} for e in self._log[-n:]]
    def save(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._path.write_text(json.dumps(self._log,indent=2))
