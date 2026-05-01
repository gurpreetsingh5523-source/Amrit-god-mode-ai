
from base_agent import BaseAgent
from context_buffer import ContextBuffer
from long_term_memory import LongTermMemory
from knowledge_store import KnowledgeStore
from experience_log import ExperienceLog
from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory
from planning_memory import PlanningMemory
import json
from pathlib import Path
from datetime import datetime

class MemoryAgent(BaseAgent):
    """Unified Memory Agent — cross-queries all memory systems."""

    def __init__(self, eb, state):
        super().__init__("MemoryAgent", eb, state)
        self.ctx      = ContextBuffer()
        self.lt       = LongTermMemory()
        self.know     = KnowledgeStore()
        self.xp       = ExperienceLog()
        self.epis     = EpisodicMemory()
        self.sem      = SemanticMemory()
        self.plan     = PlanningMemory()
        self.failures = FailurePatternDB()

    def store(self, key: str, value: dict):
        try:
            # Use state manager to persist data
            print(f"[MemoryAgent.store] Called on instance id {id(self)} for key: {key}")
            self.state.set(key, value)
            print(f"💾 [Memory] Saved: {key}")
        except Exception as e:
            print(f"[Memory] ❌ Store failed: {e}")

"""
Memory Agent — Unified Multi-Layer Memory / ਏਕੀਕ੍ਰਿਤ ਯਾਦਦਾਸ਼ਤ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UPGRADE: All 5 memory systems now TALK to each other.
    - Cross-queries ALL memory on every recall
    - Failure patterns NEVER forgotten
    - Semantic deduplication
    - Causal inference from relations
    - Auto-persist important learnings

ਹੁਣ 5 ਯਾਦਦਾਸ਼ਤ ਸਿਸਟਮ ਇੱਕ-ਦੂਜੇ ਨਾਲ ਗੱਲ ਕਰਦੇ ਹਨ।
ਗਲਤੀਆਂ ਕਦੇ ਨਹੀਂ ਭੁੱਲੀਆਂ ਜਾਂਦੀਆਂ।
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Failure Pattern DB — ਗਲਤੀਆਂ ਕਦੇ ਨਾ ਭੁੱਲੋ ───────────────
_FAILURE_DB_PATH = Path("workspace/failure_patterns.json")


class FailurePatternDB:
    """Persistent database of failure patterns — learns from every mistake."""

    def __init__(self):
        self._patterns = []
        if _FAILURE_DB_PATH.exists():
            try:
                self._patterns = json.loads(_FAILURE_DB_PATH.read_text())
            except Exception:
                self._patterns = []

    def record_failure(self, error: str, agent: str, task: str,
                       fix: str = "", worked: bool = False):
        """Record a failure and what was tried."""
        # Dedup: don't store exact same error twice
        err_key = error[:100].lower()
        for p in self._patterns:
            if p.get("error_key") == err_key:
                # Update existing pattern
                p["count"] = p.get("count", 1) + 1
                p["last_seen"] = datetime.now().isoformat()
                if fix and worked:
                    fix_text = fix[:300]
                    existing = {f.get("fix") for f in p.get("fixes", [])}
                    if fix_text not in existing and len(p["fixes"]) < 5:
                        p["fixes"].append({"fix": fix_text, "worked": True})
                self._save()
                return

        self._patterns.append({
            "error_key": err_key,
            "error": error[:500],
            "agent": agent,
            "task": task[:200],
            "fixes": [{"fix": fix[:300], "worked": worked}] if fix else [],
            "count": 1,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        })
        self._save()

    def find_fix(self, error: str) -> str:
        """Find a known fix for an error. Returns empty string if unknown."""
        err_words = set(error.lower().split()[:15])
        best_match = None
        best_overlap = 0

        for p in self._patterns:
            p_words = set(p.get("error", "").lower().split()[:15])
            overlap = len(err_words & p_words)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_match = p

        if best_match:
            # Find a fix that worked
            working_fixes = [f for f in best_match.get("fixes", []) if f.get("worked")]
            if working_fixes:
                return (f"[KNOWN FIX] Seen {best_match['count']}x before. "
                        f"Fix that worked: {working_fixes[-1]['fix']}")
            else:
                return (f"[KNOWN BUG] Seen {best_match['count']}x before. "
                        f"No working fix yet. Last attempted on agent: {best_match['agent']}")
        return ""

    def stats(self) -> dict:
        total = len(self._patterns)
        fixed = sum(1 for p in self._patterns
                    if any(f.get("worked") for f in p.get("fixes", [])))
        return {"total_patterns": total, "fixed": fixed, "unfixed": total - fixed}

    def all_patterns(self) -> list:
        return list(self._patterns)

    def _save(self):
        _FAILURE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FAILURE_DB_PATH.write_text(
            json.dumps(self._patterns[-500:], indent=2, default=str)
        )


class MemoryAgent(BaseAgent):
    """Unified Memory Agent — cross-queries all memory systems."""

    def __init__(self, eb, state):
        super().__init__("MemoryAgent", eb, state)
        self.ctx      = ContextBuffer()
        self.lt       = LongTermMemory()
        self.know     = KnowledgeStore()
        self.xp       = ExperienceLog()
        self.epis     = EpisodicMemory()
        self.sem      = SemanticMemory()
        self.plan     = PlanningMemory()
        self.failures = FailurePatternDB()

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        a = d.get("action", "store")
        await self.report(f"Memory [{a}]")
        ops = {
            "store":          self._store,
            "recall":         self._recall,
            "search":         self._unified_search,    # UPGRADED: cross-query all
            "episode":        self._episode,
            "dump":           self._dump,
            "learn_fact":     self._fact,
            "record_failure": self._record_failure,    # NEW
            "find_fix":       self._find_fix,           # NEW
            "remember_plan":  self._remember_plan,      # NEW
            "find_plan":      self._find_plan,           # NEW
            "relate":         self._add_relation,        # NEW
            "infer":          self._infer,               # NEW
            "stats":          self._stats,               # NEW
        }
        return await ops.get(a, self._store)(d)

    # ══════════════════════════════════════════════════════════════
    # STORE — Intelligent storage with auto-categorization
    # ══════════════════════════════════════════════════════════════

    async def _store(self, d):
        key = d.get("key", "")
        value = d.get("value", "")
        tags = d.get("tags", [])

        entry = {"key": key, "value": value, "tags": tags}
        self.ctx.add(entry)

        # Auto-persist important entries
        persist = d.get("persist", False)
        if persist or len(value) > 100 or "error" in str(tags).lower():
            self.lt.remember(key, value)

        # Auto-add to knowledge store if it's a fact
        if any(t in str(tags).lower() for t in ["fact", "learned", "rule", "pattern"]):
            topic = tags[0] if tags else "general"
            self.know.store(topic, f"{key}: {value}")

        return self.ok(stored=key, persisted=persist or len(value) > 100)

    # ══════════════════════════════════════════════════════════════
    # RECALL — Cross-query all memory systems
    # ══════════════════════════════════════════════════════════════

    async def _recall(self, d):
        k = d.get("key", "")

        # Query ALL memory systems
        ctx_hits = [e for e in self.ctx.get_all() if e.get("key") == k]
        lt_hit = self.lt.recall(k)
        know_hits = self.know.search(k)
        sem_hits = self.sem.search(k)
        plan_hits = self.plan.find_similar(k)

        # Check if this was a failure we've seen before
        failure_fix = self.failures.find_fix(k)

        return self.ok(
            context=ctx_hits,
            long_term=lt_hit,
            knowledge=know_hits,
            semantic=sem_hits,
            plans=plan_hits,
            failure_fix=failure_fix,
        )

    # ══════════════════════════════════════════════════════════════
    # UNIFIED SEARCH — ➕ Cross-query ALL 5+ memory systems
    # ══════════════════════════════════════════════════════════════

    async def _unified_search(self, d):
        """Search across ALL memory systems at once. This is the brain fusion."""
        q = d.get("query", "").lower()
        results = {"context": [], "knowledge": [], "semantic": [],
                   "episodes": [], "plans": [], "failures": [], "experience": []}

        # 1. Context buffer (recent short-term)
        results["context"] = [
            e for e in self.ctx.get_all()
            if q in str(e).lower()
        ][:5]

        # 2. Knowledge store (facts)
        results["knowledge"] = self.know.search(q)[:5] if hasattr(self.know, 'search') else []

        # 3. Semantic memory (concepts + relations)
        sem = self.sem.search(q)
        results["semantic"] = sem.get("relations", [])[:5]

        # 4. Episodic memory (events)
        all_episodes = self.epis.get_all() if hasattr(self.epis, 'get_all') else []
        results["episodes"] = [
            e for e in all_episodes
            if q in str(e).lower()
        ][:5]

        # 5. Planning memory (past plans)
        results["plans"] = self.plan.find_similar(q)[:3]

        # 6. Failure patterns (CRITICAL — never repeat mistakes)
        known_fix = self.failures.find_fix(q)
        if known_fix:
            results["failures"] = [known_fix]

        # 7. Experience log (agent history)
        all_xp = self.xp.get_all() if hasattr(self.xp, 'get_all') else []
        results["experience"] = [
            e for e in all_xp[-50:]
            if q in str(e).lower()
        ][:5]

        # Count total results found
        total = sum(len(v) for v in results.values() if isinstance(v, list))

        return self.ok(**results, total_results=total)

    # ══════════════════════════════════════════════════════════════
    # FAILURE TRACKING — ਗਲਤੀਆਂ ਕਦੇ ਨਾ ਭੁੱਲੋ
    # ══════════════════════════════════════════════════════════════

    async def _record_failure(self, d):
        """Record a failure pattern. NEVER lose this information."""
        self.failures.record_failure(
            error=d.get("error", ""),
            agent=d.get("agent", "unknown"),
            task=d.get("task", ""),
            fix=d.get("fix", ""),
            worked=d.get("worked", False),
        )
        # Also store in episodic memory for timeline
        self.epis.record(
            title=f"FAILURE: {d.get('agent', '?')}",
            content=d.get("error", "")[:300],
            tags=["failure", d.get("agent", "unknown")]
        )
        return self.ok(recorded=True)

    async def _find_fix(self, d):
        """Find a known fix for an error."""
        error = d.get("error", "")
        fix = self.failures.find_fix(error)
        return self.ok(fix=fix, found=bool(fix))

    # ══════════════════════════════════════════════════════════════
    # PLANNING MEMORY — ਪੁਰਾਣੀਆਂ ਯੋਜਨਾਵਾਂ ਯਾਦ ਰੱਖੋ
    # ══════════════════════════════════════════════════════════════

    async def _remember_plan(self, d):
        """Store a plan for future reuse."""
        self.plan.store(
            goal=d.get("goal", ""),
            tasks=d.get("tasks", []),
            result=d.get("result", "")
        )
        return self.ok(stored=True)

    async def _find_plan(self, d):
        """Find similar past plans."""
        similar = self.plan.find_similar(d.get("goal", ""))
        return self.ok(plans=similar, found=len(similar))

    # ══════════════════════════════════════════════════════════════
    # SEMANTIC RELATIONS — ਗਿਆਨ ਨੂੰ ਜੋੜੋ
    # ══════════════════════════════════════════════════════════════

    async def _add_relation(self, d):
        """Add a semantic relation: subject → predicate → object."""
        self.sem.add_relation(
            subject=d.get("subject", ""),
            predicate=d.get("predicate", ""),
            obj=d.get("object", "")
        )
        return self.ok(added=True)

    async def _infer(self, d):
        """Simple inference from semantic relations.
        Given 'A causes B' and 'B causes C', infer 'A may cause C'."""
        concept = d.get("concept", "")
        depth = d.get("depth", 2)

        direct = self.sem.get_relations(concept)
        inferred = list(direct)

        # Follow chains up to 'depth' steps
        visited = {concept}
        frontier = [r.get("object", "") for r in direct if r.get("subject") == concept]
        frontier += [r.get("subject", "") for r in direct if r.get("object") == concept]

        for _ in range(depth - 1):
            next_frontier = []
            for node in frontier:
                if node in visited or not node:
                    continue
                visited.add(node)
                rels = self.sem.get_relations(node)
                for r in rels:
                    if r not in inferred:
                        r["inferred"] = True
                        inferred.append(r)
                    next_frontier.append(r.get("object", ""))
                    next_frontier.append(r.get("subject", ""))
            frontier = next_frontier

        return self.ok(
            concept=concept,
            direct_relations=direct,
            all_relations=inferred,
            depth_searched=depth,
        )

    # ══════════════════════════════════════════════════════════════
    # EXISTING METHODS (kept)
    # ══════════════════════════════════════════════════════════════

    async def _episode(self, d):
        self.epis.record(title=d.get("title",""), content=d.get("content",""),
                         tags=d.get("tags",[]))
        return self.ok(recorded=True)

    async def _fact(self, d):
        self.know.store(d.get("topic","general"), d.get("fact",""))
        # Also add to semantic memory as a concept
        self.sem.add_concept(d.get("topic","general"), d.get("fact",""))
        return self.ok(learned=True)

    async def _dump(self, d):
        return self.ok(
            context=self.ctx.get_all(),
            long_term_keys=self.lt.keys(),
            topics=self.know.all_topics(),
            episodes=len(self.epis.get_all()),
            failure_stats=self.failures.stats(),
            plan_stats=self.plan.stats(),
        )

    async def _stats(self, d):
        """Full memory system statistics."""
        return self.ok(
            context_size=len(self.ctx),
            long_term_keys=len(self.lt.keys()),
            knowledge_topics=len(self.know.all_topics()),
            episodes=len(self.epis.get_all()),
            experience_total=self.xp.stats(),
            failure_patterns=self.failures.stats(),
            plans=self.plan.stats(),
        )
