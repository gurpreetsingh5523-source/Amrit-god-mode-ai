#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║  🧫 failure_dna.py — ਅਸਫ਼ਲਤਾ ਤੋਂ ਵਿਕਾਸ              ║
║                                                      ║
║  "ਹਰ failure ਇੱਕ compressed pattern ਬਣਦਾ ਹੈ"        ║
║  "ਜੋ future avoidance ਸਿੱਖਾਉਂਦਾ ਹੈ"                  ║
║  "ਅਤੇ strategy mutation trigger ਕਰਦਾ ਹੈ"            ║
║                                                      ║
║  This is meta-learning.                              ║
╚══════════════════════════════════════════════════════╝
"""

import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple
from config import CFG
from llm_client import LLMClient


class FailureDNA:
    """
    ਹਰ failure ਇੱਕ 'DNA strand' ਬਣਦਾ ਹੈ।
    ਇਹ DNA:
      1. Compress ਹੁੰਦਾ → pattern ਬਣਦਾ
      2. Recombine ਹੁੰਦਾ → avoidance strategy
      3. Mutate ਹੁੰਦਾ → ਨਵੀਂ approach
    """

    def __init__(self):
        self.db = CFG.memory_dir / "failure_dna.db"
        self.llm = LLMClient(system_prompt=
            "You analyze failure patterns and generate specific, actionable "
            "avoidance strategies. Be concrete, not generic.")
        self._init_db()
        print(f"🧫 FailureDNA — {self._count()} patterns loaded")

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS failure_strands (
                id TEXT PRIMARY KEY,
                error_type TEXT NOT NULL,
                error_message TEXT,
                module TEXT,
                context TEXT,
                count INTEGER DEFAULT 1,
                first_seen TEXT,
                last_seen TEXT,
                dna_hash TEXT,          -- compressed fingerprint
                severity REAL DEFAULT 0.5,
                resolved INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS avoidance_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_id TEXT,
                strategy TEXT NOT NULL,
                generated_by TEXT,      -- "llm" | "rule" | "human"
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                created TEXT,
                FOREIGN KEY (failure_id) REFERENCES failure_strands(id)
            );

            CREATE TABLE IF NOT EXISTS mutation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_failure_id TEXT,
                mutation_type TEXT,
                result TEXT,
                timestamp TEXT
            );
            """)

    def _count(self) -> int:
        with sqlite3.connect(self.db) as c:
            return c.execute(
                "SELECT COUNT(*) FROM failure_strands WHERE resolved=0"
            ).fetchone()[0]

    # ─────────────────────────────────────────────
    # RECORD FAILURE
    # ─────────────────────────────────────────────

    def record(self, error_type: str, error_message: str,
               module: str = "unknown", context: str = "",
               severity: float = 0.5) -> str:
        """ਅਸਫ਼ਲਤਾ ਰਿਕਾਰਡ ਕਰੋ — DNA strand ਬਣਾਓ"""
        # DNA hash — ਇੱਕੋ error ਪਛਾਣੋ
        dna_hash = hashlib.md5(
            f"{error_type}{module}{error_message[:50]}".encode()
        ).hexdigest()[:12]

        gen_strategy = False  # decide inside, run AFTER connection closes (avoid lock)
        with sqlite3.connect(self.db, timeout=10) as c:
            c.execute("PRAGMA busy_timeout=10000")
            existing = c.execute(
                "SELECT id, count FROM failure_strands WHERE dna_hash=?",
                (dna_hash,)
            ).fetchone()

            if existing:
                fid = existing[0]
                new_count = existing[1] + 1
                c.execute("""
                    UPDATE failure_strands SET
                        count=?, last_seen=?,
                        severity=MIN(1.0, severity + 0.05)
                    WHERE id=?
                """, (new_count, datetime.now().isoformat(), fid))
                print(f"  ❌ Failure #{new_count}: {error_type[:50]}")
                # ਜ਼ਿਆਦਾ ਵਾਰ → LLM strategy generate ਕਰੋ (connection ਬੰਦ ਹੋਣ ਤੋਂ ਬਾਅਦ)
                if new_count in [3, 7, 15]:
                    gen_strategy = True
            else:
                fid = f"f_{dna_hash}"
                c.execute("""
                    INSERT INTO failure_strands
                    (id, error_type, error_message, module, context,
                     dna_hash, severity, first_seen, last_seen)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (fid, error_type, error_message[:500], module,
                      context[:200], dna_hash, severity,
                      datetime.now().isoformat(),
                      datetime.now().isoformat()))
                print(f"  ❌ New failure DNA: {error_type[:50]}")

        # Strategy generation opens its own connection — must be OUTSIDE the
        # `with` above, else SQLite deadlocks ("database is locked").
        if gen_strategy:
            self._generate_strategy(fid, error_type, error_message)

        return fid

    # ─────────────────────────────────────────────
    # STRATEGY GENERATION
    # ─────────────────────────────────────────────

    def _generate_strategy(self, failure_id: str,
                           error_type: str, error_message: str):
        """LLM ਤੋਂ avoidance strategy ਲਵੋ"""
        print(f"  🧬 Strategy generating for: {error_type[:40]}...")

        # ਪਿਛਲੀਆਂ strategies ਦੇਖੋ
        with sqlite3.connect(self.db) as c:
            existing = c.execute("""
                SELECT strategy FROM avoidance_strategies
                WHERE failure_id=?
            """, (failure_id,)).fetchall()

        past_strategies = [r[0] for r in existing]

        prompt = f"""Failure Analysis:
Error Type: {error_type}
Error Message: {error_message[:300]}

{"Past strategies tried (that didn't fully work): " + str(past_strategies[:2]) if past_strategies else "No strategies tried yet."}

Generate ONE specific, actionable avoidance strategy.
Format: [DETECT: how to detect early] | [PREVENT: how to prevent] | [RECOVER: how to recover]
Be concrete. No generic advice."""

        strategy = self.llm.ask(prompt)

        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO avoidance_strategies
                (failure_id, strategy, generated_by, created)
                VALUES (?,?,?,?)
            """, (failure_id, strategy, "llm",
                  datetime.now().isoformat()))

        print(f"  ✅ Strategy: {strategy[:100]}...")
        return strategy

    def generate_strategy_now(self, failure_id: str) -> str:
        """ਹੁਣੇ strategy ਬਣਾਓ"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT * FROM failure_strands WHERE id=?", (failure_id,)
            ).fetchone()
        if row:
            return self._generate_strategy(failure_id, row[1], row[2])
        return "Failure not found"

    # ─────────────────────────────────────────────
    # MUTATION
    # ─────────────────────────────────────────────

    def mutate(self, failure_id: str) -> str:
        """
        ਅਸਫ਼ਲਤਾ ਤੋਂ ਨਵੀਂ approach:
        Strategy ਬਦਲੋ — ਵੱਖਰੀ ਦਿਸ਼ਾ
        """
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            failure = c.execute(
                "SELECT * FROM failure_strands WHERE id=?", (failure_id,)
            ).fetchone()
            strategies = c.execute("""
                SELECT strategy FROM avoidance_strategies
                WHERE failure_id=? ORDER BY success_count DESC
            """, (failure_id,)).fetchall()

        if not failure:
            return "Failure not found"

        prompt = f"""Mutation Task — Generate a radically different approach:

Original failure: {failure['error_type']}
Message: {failure['error_message'][:200]}
Occurred: {failure['count']} times

Past strategies (none fully worked):
{chr(10).join([s[0][:100] for s in strategies[:3]])}

Suggest a COMPLETELY DIFFERENT approach.
Think from first principles — not incremental fixes.
What fundamental assumption needs to change?"""

        mutation = self.llm.ask(prompt)

        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO mutation_log
                (parent_failure_id, mutation_type, result, timestamp)
                VALUES (?,?,?,?)
            """, (failure_id, "radical_rethink", mutation,
                  datetime.now().isoformat()))

        print(f"\n🧬 Mutation for {failure['error_type'][:40]}:")
        print(f"   {mutation[:200]}")
        return mutation

    # ─────────────────────────────────────────────
    # LOOKUP & PREVENTION
    # ─────────────────────────────────────────────

    def should_avoid(self, action_description: str) -> Tuple[bool, str]:
        """
        ਕੋਈ action ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ — ਕੀ ਇਹ ਪਹਿਲਾਂ ਫੇਲ ਹੋਇਆ?
        Returns: (should_avoid, reason)
        """
        words = action_description.lower().split()[:5]
        with sqlite3.connect(self.db) as c:
            for word in words:
                if len(word) < 4:
                    continue
                row = c.execute("""
                    SELECT error_type, count, severity
                    FROM failure_strands
                    WHERE LOWER(error_message) LIKE ?
                       OR LOWER(context) LIKE ?
                    AND resolved=0
                    ORDER BY count DESC LIMIT 1
                """, (f"%{word}%", f"%{word}%")).fetchone()
                if row and row[1] >= 3 and row[2] > 0.6:
                    return True, f"ਇਹ pattern {row[1]} ਵਾਰ ਫੇਲ ਹੋਇਆ: {row[0]}"
        return False, "ਕੋਈ matching failure ਨਹੀਂ"

    def get_top_failures(self, n: int = 5) -> List[Dict]:
        """ਸਭ ਤੋਂ ਵੱਧ ਹੋਣ ਵਾਲੀਆਂ ਅਸਫ਼ਲਤਾਵਾਂ"""
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT f.*, GROUP_CONCAT(a.strategy, ' | ') as strategies
                FROM failure_strands f
                LEFT JOIN avoidance_strategies a ON f.id = a.failure_id
                WHERE f.resolved=0
                GROUP BY f.id
                ORDER BY f.count DESC, f.severity DESC
                LIMIT ?
            """, (n,)).fetchall()
            return [dict(r) for r in rows]

    def mark_resolved(self, failure_id: str):
        """ਅਸਫ਼ਲਤਾ ਹੱਲ ਹੋਈ"""
        with sqlite3.connect(self.db) as c:
            c.execute(
                "UPDATE failure_strands SET resolved=1 WHERE id=?",
                (failure_id,)
            )
        print(f"  ✅ Failure {failure_id} resolved!")

    def status(self) -> Dict:
        with sqlite3.connect(self.db) as c:
            total    = c.execute("SELECT COUNT(*) FROM failure_strands").fetchone()[0]
            active   = c.execute("SELECT COUNT(*) FROM failure_strands WHERE resolved=0").fetchone()[0]
            strats   = c.execute("SELECT COUNT(*) FROM avoidance_strategies").fetchone()[0]
            muts     = c.execute("SELECT COUNT(*) FROM mutation_log").fetchone()[0]
        return {
            "total_failures":   total,
            "active_failures":  active,
            "strategies":       strats,
            "mutations":        muts
        }

    def print_report(self):
        top = self.get_top_failures(5)
        print("\n🧫 FAILURE DNA REPORT")
        print("─"*50)
        for f in top:
            print(f"  [{f['count']}x] {f['error_type'][:40]}")
            if f['strategies']:
                print(f"    → {f['strategies'][:80]}...")
        s = self.status()
        print(f"\n  Active: {s['active_failures']} | "
              f"Strategies: {s['strategies']} | "
              f"Mutations: {s['mutations']}")


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    fdna = FailureDNA()

    # ਕੁਝ failures ਰਿਕਾਰਡ ਕਰੋ
    f1 = fdna.record("ConnectionTimeout", "Ollama did not respond in 60s",
                     module="llm_client", severity=0.7)
    fdna.record("ConnectionTimeout", "Ollama did not respond in 60s",
                module="llm_client", severity=0.7)
    fdna.record("ConnectionTimeout", "Ollama did not respond in 60s",
                module="llm_client", severity=0.7)

    fdna.record("SQLConstraintError", "UNIQUE constraint failed: skills.name",
                module="self_graph", severity=0.4)

    # Strategy ਬਣਾਓ
    fdna.generate_strategy_now(f1)

    # Mutation
    fdna.mutate(f1)

    # Report
    fdna.print_report()

    # Prevention check
    avoid, reason = fdna.should_avoid("call ollama for large prompt")
    print(f"\n⚠️  Avoid action? {avoid} — {reason}")
