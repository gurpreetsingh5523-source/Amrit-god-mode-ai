"""Embedding Model — Ollama nomic-embed-text (primary) + sentence_transformers (fallback)."""
import math
import json
import urllib.request
import urllib.error
from logger import setup_logger
logger = setup_logger("EmbeddingModel")

OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_EMBED_MODEL = "nomic-embed-text"


def _ollama_embed(text: str) -> list:
    """Call Ollama nomic-embed-text for embedding. Returns list of floats or []."""
    try:
        payload = json.dumps({"model": OLLAMA_EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data.get("embedding", [])
    except Exception as e:
        logger.debug(f"Ollama embed failed: {e}")
        return []


class EmbeddingModel:
    """Embedding backend: Ollama nomic-embed-text → sentence_transformers → hash fallback."""

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self._st_model_name = model
        self._st = None          # lazy-loaded sentence_transformers
        self._dims = None        # detected embedding dimensions

    def _ensure_st(self):
        if self._st is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._st = SentenceTransformer(self._st_model_name)
            except Exception:
                self._st = False  # mark as unavailable

    def embed(self, text: str) -> list:
        """Return embedding vector for text. Never raises — falls back to hash."""
        if not isinstance(text, str) or not text.strip():
            return self._hash_embed(text or "")

        # Primary: Ollama nomic-embed-text
        vec = _ollama_embed(text)
        if vec:
            self._dims = len(vec)
            return vec

        # Fallback: sentence_transformers
        self._ensure_st()
        if self._st:
            try:
                v = self._st.encode(text, normalize_embeddings=True).tolist()
                self._dims = len(v)
                return v
            except Exception:
                pass

        # Last resort: deterministic hash-based pseudo-embedding (dim=64)
        return self._hash_embed(text)

    def embed_batch(self, texts: list) -> list:
        """Embed multiple texts. Uses Ollama for each, batches sentence_transformers."""
        if not texts:
            return []

        # Try Ollama one-by-one (fast enough for small batches)
        results = [_ollama_embed(t) for t in texts]
        if all(results):
            return results

        # Try sentence_transformers batch
        self._ensure_st()
        if self._st:
            try:
                return [v.tolist() for v in
                        self._st.encode(texts, normalize_embeddings=True)]
            except Exception:
                pass

        return [self.embed(t) for t in texts]

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed(a), self.embed(b)
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(x * x for x in vb))
        return round(dot / (na * nb + 1e-9), 4)

    def _hash_embed(self, text: str, dims: int = 64) -> list:
        """Deterministic pseudo-embedding from hash. Used only when all else fails."""
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        vals = [(b / 127.5) - 1.0 for b in h]  # 32 values in [-1, 1]
        # Repeat to reach desired dims
        while len(vals) < dims:
            vals.extend(vals)
        vals = vals[:dims]
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]
