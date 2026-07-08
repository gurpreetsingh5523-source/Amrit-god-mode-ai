"""Semantic Memory — Concept relationships and semantic network."""
import json
from pathlib import Path

class SemanticMemory:
    def __init__(self, path="workspace/semantic.json"):
        self._concepts = {}
        self._relations = []
        self._path = Path(path)
        if self._path.exists():
            try:
                d = json.loads(self._path.read_text())
                self._concepts = d.get("concepts",{})
                self._relations = d.get("relations",[])
            except Exception:
                pass

    def add_concept(self, name: str, description: str, properties=None):
        self._concepts[name] = {"description":description,"properties":properties or {}}
        self.save()

    def add_relation(self, subject: str, predicate: str, obj: str):
        rel = {"subject":subject,"predicate":predicate,"object":obj}
        if rel not in self._relations:
            self._relations.append(rel)
            self.save()

    def get_relations(self, concept: str) -> list:
        return [r for r in self._relations if r["subject"]==concept or r["object"]==concept]

    def search(self, query: str) -> dict:
        q = query.lower()
        concepts = {k:v for k,v in self._concepts.items() if q in k.lower() or q in str(v).lower()}
        relations= [r for r in self._relations if q in str(r).lower()]
        return {"concepts":concepts,"relations":relations}

    def save(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._path.write_text(json.dumps({"concepts":self._concepts,"relations":self._relations},indent=2))
