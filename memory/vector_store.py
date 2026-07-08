"""Vector Store — Cosine similarity search over embeddings."""
import json
import math
from pathlib import Path
from logger import setup_logger
logger = setup_logger("VectorStore")

def _cos(a,b):
    dot=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a))
    nb=math.sqrt(sum(x*x for x in b))
    return dot/(na*nb+1e-9)

class VectorStore:
    def __init__(self, path="workspace/vectors.json"):
        self._store = []
        self._path = Path(path)
        if self._path.exists():
            try:
                self._store = json.loads(self._path.read_text())
            except Exception:
                pass

    def add(self, text: str, embedding: list, metadata=None, doc_id=None):
        entry = {"id":doc_id or str(len(self._store)),"text":text,"embedding":embedding,"metadata":metadata or {}}
        self._store = [e for e in self._store if e["id"] != entry["id"]]
        self._store.append(entry)

    def search(self, q_emb: list, top_k=5, filter_fn=None) -> list:
        cands = [e for e in self._store if not filter_fn or filter_fn(e)]
        if not cands:
            return []
        scored = sorted(cands, key=lambda e: -_cos(q_emb, e["embedding"]))
        return [{"text":e["text"],"score":round(_cos(q_emb,e["embedding"]),4),
                 "metadata":e["metadata"],"id":e["id"]} for e in scored[:top_k]]

    def delete(self, doc_id: str): self._store = [e for e in self._store if e["id"] != doc_id]
    def count(self) -> int: return len(self._store)
    def save(self):
        self._path.parent.mkdir(parents=True,exist_ok=True)
        self._path.write_text(json.dumps(self._store))
