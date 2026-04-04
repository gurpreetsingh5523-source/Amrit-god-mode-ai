"""Episodic Memory — Stores named episodes/events with context."""
import json
from datetime import datetime
from pathlib import Path

class EpisodicMemory:
    def __init__(self, path="workspace/episodes.json"):
        self._episodes = []; self._path = Path(path)
        if self._path.exists():
            try: self._episodes = json.loads(self._path.read_text())
            except: pass

    def record(self, title: str, content: str, tags=None, agents=None):
        episode = {"id": len(self._episodes)+1, "title":title, "content":content,
                   "tags":tags or [], "agents":agents or [],
                   "timestamp":datetime.now().isoformat()}
        self._episodes.append(episode); self.save()
        return episode

    def search(self, query: str) -> list:
        q = query.lower()
        return [e for e in self._episodes if q in e["title"].lower() or q in e["content"].lower()]

    def by_tag(self, tag: str) -> list:
        return [e for e in self._episodes if tag in e.get("tags",[])]

    def get_all(self) -> list: return list(self._episodes)
    def recent(self, n=10) -> list: return self._episodes[-n:]
    def save(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._path.write_text(json.dumps(self._episodes,indent=2))
