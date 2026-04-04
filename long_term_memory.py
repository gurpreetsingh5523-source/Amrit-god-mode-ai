"""Long-Term Memory — Persistent JSON key-value store with tags and search."""
import json
from pathlib import Path
from datetime import datetime
from logger import setup_logger
logger = setup_logger("LongTermMemory")

class LongTermMemory:
    def __init__(self, path="workspace/memory.json"):
        self.path = Path(path); self._data = {}; self._meta = {}; self.load()

    def remember(self, key: str, value, tags=None):
        self._data[key] = value
        self._meta[key] = {"updated": datetime.now().isoformat(),
                           "created": self._meta.get(key,{}).get("created",datetime.now().isoformat()),
                           "tags": tags or []}
        self.save()

    def recall(self, key: str, default=None): return self._data.get(key, default)
    def forget(self, key: str): self._data.pop(key,None); self._meta.pop(key,None); self.save()

    def search(self, q: str) -> dict:
        return {k:v for k,v in self._data.items() if q.lower() in k.lower() or q.lower() in str(v).lower()}

    def by_tag(self, tag: str) -> dict:
        return {k:self._data[k] for k,m in self._meta.items() if tag in m.get("tags",[])}

    def keys(self) -> list: return list(self._data.keys())

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path,"w") as f: json.dump({"data":self._data,"meta":self._meta},f,indent=2,default=str)

    def load(self):
        if self.path.exists():
            try:
                p = json.loads(self.path.read_text())
                self._data = p.get("data",{}); self._meta = p.get("meta",{})
                logger.info(f"Memory loaded: {len(self._data)} entries")
            except Exception as e: logger.warning(f"Load error: {e}")
