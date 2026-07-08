"""Knowledge Store — Topic-based fact database with semantic vector search."""
import json
from pathlib import Path
from logger import setup_logger
logger = setup_logger("KnowledgeStore")


class KnowledgeStore:
    """
    Stores facts by topic (keyword DB) AND as semantic vectors (VectorStore).
    - store(topic, fact)     → saves to both
    - search(q)              → semantic search first, keyword fallback
    - retrieve(topic)        → exact topic lookup
    """

    def __init__(self, path: str = "workspace/knowledge.json"):
        self._facts: dict = {}
        self._path = Path(path)
        if self._path.exists():
            try:
                self._facts = json.loads(self._path.read_text())
            except Exception:
                pass

        # Lazy-init heavy components
        self._vs = None
        self._em = None

    def _get_vs(self):
        """Lazy-load VectorStore."""
        if self._vs is None:
            try:
                from vector_store import VectorStore
                self._vs = VectorStore("workspace/knowledge_vectors.json")
            except Exception as e:
                logger.debug(f"VectorStore unavailable: {e}")
                self._vs = False
        return self._vs if self._vs else None

    def _get_em(self):
        """Lazy-load EmbeddingModel."""
        if self._em is None:
            try:
                from embedding_model import EmbeddingModel
                self._em = EmbeddingModel()
            except Exception as e:
                logger.debug(f"EmbeddingModel unavailable: {e}")
                self._em = False
        return self._em if self._em else None

    def store(self, topic: str, fact: str):
        """Store a fact under a topic. Also indexes into vector store."""
        t = topic.strip().lower()
        self._facts.setdefault(t, [])
        if fact not in self._facts[t]:
            self._facts[t].append(fact)
            self.save()
            # Index into vector store
            self._index_fact(t, fact)

    def _index_fact(self, topic: str, fact: str):
        """Embed fact and add to vector store."""
        vs = self._get_vs()
        em = self._get_em()
        if not vs or not em:
            return
        try:
            vec = em.embed(f"{topic}: {fact}")
            if vec:
                doc_id = f"{topic}::{hash(fact) & 0xFFFFFF:06x}"
                vs.add(text=fact, embedding=vec,
                       metadata={"topic": topic}, doc_id=doc_id)
                vs.save()
        except Exception as e:
            logger.debug(f"Vector index failed: {e}")

    def search(self, q: str, top_k: int = 5) -> dict:
        """
        Semantic search first (via embeddings), keyword fallback.
        Returns {topic: [facts]} dict.
        """
        vs = self._get_vs()
        em = self._get_em()

        if vs and em:
            try:
                q_vec = em.embed(q)
                if q_vec:
                    hits = vs.search(q_vec, top_k=top_k)
                    if hits:
                        results = {}
                        for h in hits:
                            topic = h["metadata"].get("topic", "unknown")
                            results.setdefault(topic, [])
                            results[topic].append(h["text"])
                        logger.debug(f"Semantic search '{q}': {len(hits)} hits")
                        return results
            except Exception as e:
                logger.debug(f"Semantic search failed, falling back: {e}")

        # Keyword fallback
        return {t: f for t, f in self._facts.items()
                if q.lower() in t or any(q.lower() in x.lower() for x in f)}

    def retrieve(self, topic: str) -> list:
        """Exact topic lookup."""
        return self._facts.get(topic.lower(), [])

    def all_topics(self) -> list:
        return sorted(self._facts.keys())

    def reindex_all(self):
        """Re-embed all facts into vector store (run after adding many facts)."""
        vs = self._get_vs()
        em = self._get_em()
        if not vs or not em:
            logger.warning("Vector store or embedding model unavailable")
            return
        count = 0
        for topic, facts in self._facts.items():
            for fact in facts:
                self._index_fact(topic, fact)
                count += 1
        logger.info(f"Reindexed {count} facts into vector store")

    def export_md(self) -> str:
        lines = ["# Knowledge Base"]
        for t in sorted(self._facts):
            lines += [f"\n## {t.title()}"] + [f"- {f}" for f in self._facts[t]]
        return "\n".join(lines)

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._facts, indent=2))

