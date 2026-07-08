#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║  🧬 self_graph.py — Amrit ਦਾ ਸਥਾਈ ਸਵੈ-ਮਾਡਲ               ║
║                                                              ║
║  "ਮੈਂ ਕੀ ਹਾਂ? ਮੈਂ ਕੀ ਸਿੱਖਿਆ? ਮੈਂ ਕਿੱਥੇ ਅਸਫ਼ਲ ਹੋਇਆ?"     ║
║                                                              ║
║  ਇਹ ਉਹ layer ਹੈ ਜੋ system ਨੂੰ ਹਰ run ਵਿੱਚ                ║
║  ਆਪਣਾ ਇਤਿਹਾਸ ਯਾਦ ਰੱਖਣ ਦਿੰਦੀ ਹੈ।                         ║
║                                                              ║
║  Tracks: skills | failures | goals | identity | evolution   ║
╚══════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
from config import CFG
from llm_client import LLMClient


# ══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════

@dataclass
class SkillNode:
    """ਇੱਕ ਸਿੱਖੀ ਹੋਈ skill"""
    id: str
    name: str
    description: str
    category: str          # "research" | "coding" | "reasoning" | "creative"
    success_count: int = 0
    failure_count: int = 0
    last_used: str = ""
    confidence: float = 0.5
    code_ref: str = ""     # ਸਕਿੱਲ ਦੀ file ਦਾ ਰਸਤਾ

@dataclass
class GoalNode:
    """ਇੱਕ ਟੀਚਾ — ਪੂਰਾ ਜਾਂ ਅਧੂਰਾ"""
    id: str
    description: str
    status: str            # "active" | "complete" | "abandoned"
    priority: float = 0.5
    progress: float = 0.0
    created: str = ""
    completed: str = ""
    sub_goals: List[str] = None

    def __post_init__(self):
        if self.sub_goals is None:
            self.sub_goals = []

@dataclass
class IdentitySnapshot:
    """ਸਮੇਂ ਅਨੁਸਾਰ ਸਵੈ-ਤਸਵੀਰ"""
    timestamp: str
    wisdom_level: float
    skill_count: int
    goal_count: int
    failure_patterns: List[str]
    strengths: List[str]
    self_description: str  # LLM-generated


# ══════════════════════════════════════════════════════════════
# SELF GRAPH — ਮੁੱਖ ਕਲਾਸ
# ══════════════════════════════════════════════════════════════

class SelfGraph:
    """
    ਅਮ੍ਰਿਤ ਦੀ ਸਥਾਈ ਸਵੈ-ਜਾਣਕਾਰੀ।

    ਹਰ run ਵਿੱਚ:
    - ਕੀ ਸਿੱਖਿਆ ✓
    - ਕੀ ਭੁੱਲਿਆ ✓
    - ਕਿੱਥੇ fail ਹੋਇਆ ✓
    - ਕਿਹੜੇ goals ਅਧੂਰੇ ✓
    - ਮੈਂ ਕੀ ਬਣ ਰਿਹਾ ਹਾਂ ✓
    """

    def __init__(self) -> None:
        """Initialize SelfGraph with database and LLM client.

        Sets up the self-reflection engine by initializing the database connection,
        LLM client with a system prompt, and loading the current state. Logs
        initialization progress and prints a status summary upon success.

        Args:
            None

        Returns:
            None

        Raises:
            AttributeError: If required configuration attributes are missing.
            ValueError: If invalid values are provided during initialization.
            TypeError: If type mismatches occur during initialization.
            Exception: For any other unexpected errors during initialization.
        """
        from logger import setup_logger
        logger = setup_logger(__name__)
        try:
            logger.info("Initializing SelfGraph with key params: db=%s, llm_system_prompt=%s", CFG.self_db, "You are the self-reflection engine of Amrit AI. Analyze the system's state honestly and concisely.")
            self.db = CFG.self_db
            self.llm = LLMClient(system_prompt=
                "You are the self-reflection engine of Amrit AI. "
                "Analyze the system's state honestly and concisely.")
            logger.debug("Calling _init_db()")
            self._init_db()
            logger.debug("Calling _load_state()")
            self._load_state()
            logger.debug("Printing status: skills=%d, active_goals=%d", self.skill_count(), self.active_goal_count())
            print(f"🧬 SelfGraph ਜਾਗਿਆ — {self.skill_count()} skills, "
                  f"{self.active_goal_count()} active goals")
        except AttributeError as e:
            logger.error("Attribute error during initialization: %s", e)
            raise
        except ValueError as e:
            logger.error("Value error during initialization: %s", e)
            raise
        except TypeError as e:
            logger.error("Type error during initialization: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during initialization: %s", e)
            raise

    # ─────────────────────────────────────────────
    # DATABASE SETUP
    # ─────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                category TEXT,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_used TEXT,
                confidence REAL DEFAULT 0.5,
                code_ref TEXT
            );

            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                priority REAL DEFAULT 0.5,
                progress REAL DEFAULT 0.0,
                created TEXT,
                completed TEXT,
                sub_goals TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                context TEXT,
                module TEXT,
                count INTEGER DEFAULT 1,
                first_seen TEXT,
                last_seen TEXT,
                resolved INTEGER DEFAULT 0,
                avoidance_strategy TEXT
            );

            CREATE TABLE IF NOT EXISTS evolution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                description TEXT,
                delta_wisdom REAL DEFAULT 0,
                snapshot TEXT
            );

            CREATE TABLE IF NOT EXISTS identity (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                wisdom_level REAL,
                skill_count INTEGER,
                goal_count INTEGER,
                failure_patterns TEXT,
                strengths TEXT,
                self_description TEXT
            );
            """)

    def _load_state(self):
        """ਪਿਛਲੀ state ਯਾਦ ਕਰੋ"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT wisdom_level FROM identity ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.wisdom = row[0] if row else 0.1

    # ─────────────────────────────────────────────
    # SKILL MANAGEMENT
    # ─────────────────────────────────────────────

    def learn_skill(self, name: str, description: str,
                    category: str = "general", code_ref: str = "") -> str:
        """ਨਵੀਂ skill ਸਿੱਖੋ"""
        from logger import setup_logger
        logger = setup_logger(__name__)
        logger.info(f"Entering learn_skill with name={name}, description={description}, category={category}, code_ref={code_ref}")
        try:
            sid = hashlib.sha256(name.encode()).hexdigest()[:10]
            logger.debug(f"Generated skill ID: {sid}")
            with sqlite3.connect(self.db) as c:
                c.execute("""
                    INSERT OR REPLACE INTO skills
                    (id, name, description, category, last_used, code_ref)
                    VALUES (?,?,?,?,?,?)
                """, (sid, name, description, category,
                      datetime.now().isoformat(), code_ref))
                logger.debug(f"Inserted skill {sid} into database")
            self._log_evolution("skill_learned", f"ਨਵੀਂ skill: {name}", 0.02)
            print(f"  🧬 Skill ਸਿੱਖਿਆ: [{category}] {name}")
            return sid
        except Exception as e:
            logger.error(f"Error in learn_skill: {e}")
            raise

    def skill_succeeded(self, skill_name: str) -> None:
        """Skill ਕਾਮਯਾਬ ਹੋਈ"""
        with sqlite3.connect(self.db) as c:
            c.execute("""
                UPDATE skills SET
                    success_count = success_count + 1,
                    confidence = MIN(1.0, confidence + 0.05),
                    last_used = ?
                WHERE name = ?
            """, (datetime.now().isoformat(), skill_name))

    def skill_failed(self, skill_name: str) -> None:
        """Skill ਅਸਫ਼ਲ ਹੋਈ"""
        with sqlite3.connect(self.db) as c:
            c.execute("""
                UPDATE skills SET
                    failure_count = failure_count + 1,
                    confidence = MAX(0.1, confidence - 0.08),
                    last_used = ?
                WHERE name = ?
            """, (datetime.now().isoformat(), skill_name))

    def get_best_skills(self, category: str = None, limit: int = 5) -> List[Dict]:
        """ਸਭ ਤੋਂ ਵਧੀਆ skills"""
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            if category:
                rows = c.execute("""
                    SELECT * FROM skills WHERE category=?
                    ORDER BY confidence DESC, success_count DESC LIMIT ?
                """, (category, limit)).fetchall()
            else:
                rows = c.execute("""
                    SELECT * FROM skills
                    ORDER BY confidence DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_weak_skills(self, limit: int = 5) -> List[Dict]:
        """ਕਮਜ਼ੋਰ skills — ਸੁਧਾਰ ਦੀ ਲੋੜ"""
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT * FROM skills
                WHERE failure_count > success_count
                ORDER BY confidence ASC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def skill_count(self) -> int:
        with sqlite3.connect(self.db) as c:
            return c.execute("SELECT COUNT(*) FROM skills").fetchone()[0]

    # ─────────────────────────────────────────────
    # GOAL MANAGEMENT
    # ─────────────────────────────────────────────

    def set_goal(self, description: str, priority: float = 0.5,
                 sub_goals: List[str] = None) -> str:
        """ਨਵਾਂ ਟੀਚਾ ਰੱਖੋ"""
        logger.info(f"Setting goal: description='{description}', priority={priority}, sub_goals={sub_goals}")
        gid = hashlib.sha256(
            f"{description}{time.time()}".encode()
        ).hexdigest()[:10]
        logger.debug(f"Generated goal ID: {gid}")
        try:
            with sqlite3.connect(self.db) as c:
                logger.debug("Inserting goal into database")
                c.execute("""
                    INSERT INTO goals (id, description, priority, created, sub_goals)
                    VALUES (?,?,?,?,?)
                """, (gid, description, priority,
                      datetime.now().isoformat(),
                      json.dumps(sub_goals or [])))
                logger.debug("Goal inserted successfully")
        except Exception as e:
            logger.error(f"Failed to set goal: {e}")
            raise
        logger.debug("Logging evolution and printing confirmation")
        self._log_evolution("goal_set", f"ਨਵਾਂ ਟੀਚਾ: {description[:60]}", 0.01)
        print(f"  🎯 Goal ਰੱਖਿਆ: {description[:60]}")
        return gid

    def update_goal_progress(self, goal_id: str, progress: float):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "UPDATE goals SET progress=? WHERE id=?",
                (min(1.0, progress), goal_id)
            )
            if progress >= 1.0:
                c.execute(
                    "UPDATE goals SET status='complete', completed=? WHERE id=?",
                    (datetime.now().isoformat(), goal_id)
                )
                self._log_evolution("goal_complete",
                    f"Goal {goal_id} ਪੂਰਾ ਹੋਇਆ", 0.05)

    def get_active_goals(self) -> List[Dict]:
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT * FROM goals WHERE status='active'
                ORDER BY priority DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def active_goal_count(self) -> int:
        with sqlite3.connect(self.db) as c:
            return c.execute(
                "SELECT COUNT(*) FROM goals WHERE status='active'"
            ).fetchone()[0]

    # ─────────────────────────────────────────────
    # FAILURE DNA
    # ─────────────────────────────────────────────

    def record_failure(self, pattern: str, context: str = "",
                       module: str = "unknown") -> None:
        """ਅਸਫ਼ਲਤਾ ਰਿਕਾਰਡ ਕਰੋ — ਸਿੱਖਣ ਲਈ"""
        from logger import setup_logger
        logger = setup_logger(__name__)
        logger.info(f"record_failure called with pattern={pattern}, context={context}, module={module}")
        try:
            with sqlite3.connect(self.db) as c:
                logger.debug(f"Querying database for pattern: {pattern}")
                existing = c.execute(
                    "SELECT id, count FROM failures WHERE pattern=?", (pattern,)
                ).fetchone()
                if existing:
                    logger.debug(f"Existing failure found with id={existing[0]}, count={existing[1]}")
                    c.execute("""
                        UPDATE failures SET count=count+1, last_seen=? WHERE id=?
                    """, (datetime.now().isoformat(), existing[0]))
                else:
                    logger.debug("No existing failure found, inserting new record")
                    c.execute("""
                        INSERT INTO failures
                        (pattern, context, module, first_seen, last_seen)
                        VALUES (?,?,?,?,?)
                    """, (pattern, context, module,
                          datetime.now().isoformat(),
                          datetime.now().isoformat()))
            print(f"  ❌ Failure ਰਿਕਾਰਡ: {pattern[:60]}")
        except Exception as e:
            logger.error(f"Error recording failure: {e}")
            raise

    def get_failure_patterns(self, top: int = 10) -> List[Dict]:
        """ਵਾਰ-ਵਾਰ ਆਉਂਦੀਆਂ ਅਸਫ਼ਲਤਾਵਾਂ"""
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT * FROM failures WHERE resolved=0
                ORDER BY count DESC LIMIT ?
            """, (top,)).fetchall()
            return [dict(r) for r in rows]

    def resolve_failure(self, failure_id: int, strategy: str) -> None:
        """ਅਸਫ਼ਲਤਾ ਦਾ ਹੱਲ ਮਿਲਿਆ"""
        from logger import setup_logger
        logger = setup_logger(__name__)
        logger.info(f"Resolving failure: failure_id={failure_id}, strategy={strategy}")
        try:
            with sqlite3.connect(self.db) as c:
                logger.debug(f"Connected to database: {self.db}")
                c.execute("""
                    UPDATE failures SET resolved=1, avoidance_strategy=? WHERE id=?
                """, (strategy, failure_id))
                logger.debug(f"Updated failure {failure_id} with strategy '{strategy}'")
            self._log_evolution("failure_resolved",
                f"Failure {failure_id} ਹੱਲ ਹੋਇਆ", 0.03)
            logger.debug(f"Logged evolution for failure {failure_id}")
        except Exception as e:
            logger.error(f"Failed to resolve failure {failure_id}: {e}")
            raise

    # ─────────────────────────────────────────────
    # EVOLUTION LOGGING
    # ─────────────────────────────────────────────

    def _log_evolution(self, event_type: str, description: str,
                       delta_wisdom: float = 0):
        """ਵਿਕਾਸ ਦਾ ਰਿਕਾਰਡ"""
        self.wisdom = min(1.0, self.wisdom + delta_wisdom)
        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO evolution_log
                (timestamp, event_type, description, delta_wisdom)
                VALUES (?,?,?,?)
            """, (datetime.now().isoformat(), event_type,
                  description, delta_wisdom))

    def get_evolution_history(self, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT * FROM evolution_log
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    # SELF REFLECTION — LLM-ਅਧਾਰਤ
    # ─────────────────────────────────────────────

    def reflect(self) -> IdentitySnapshot:
        """
        LLM ਤੋਂ ਆਪਣੇ ਬਾਰੇ ਪੁੱਛੋ:
        'ਮੈਂ ਕੀ ਹਾਂ? ਮੇਰੀਆਂ ਤਾਕਤਾਂ ਅਤੇ ਕਮਜ਼ੋਰੀਆਂ ਕੀ ਹਨ?'
        """
        from logger import setup_logger
        logger = setup_logger(__name__)
        logger.info("reflect() called with wisdom=%.3f, skill_count=%d", self.wisdom, self.skill_count())

        skills    = self.get_best_skills(limit=5)
        weak      = self.get_weak_skills(limit=3)
        failures  = self.get_failure_patterns(top=5)
        goals     = self.get_active_goals()

        logger.debug("Retrieved %d best skills, %d weak skills, %d failure patterns, %d active goals", 
                     len(skills), len(weak), len(failures), len(goals))

        prompt = f"""Amrit AI System Self-Reflection:

    CURRENT STATE:
    - Wisdom level: {self.wisdom:.3f}
    - Total skills: {self.skill_count()}
    - Active goals: {len(goals)}

    STRONGEST SKILLS: {[s['name'] for s in skills]}
    WEAKEST SKILLS: {[s['name'] for s in weak]}

    TOP FAILURE PATTERNS:
    {chr(10).join([f"- {f['pattern']} (occurred {f['count']} times)" for f in failures[:3]])}

    ACTIVE GOALS:
    {chr(10).join([f"- {g['description'][:80]} [{g['progress']*100:.0f}%]" for g in goals[:3]])}

    Write a honest 2-sentence self-assessment:
    1. What am I good at?
    2. What must I improve?
    Keep it specific, not generic."""

        self_description = self.llm.ask(prompt)
        logger.debug("LLM returned self_description of length %d", len(self_description))

        strengths = [s['name'] for s in skills]
        failure_patterns = [f['pattern'][:50] for f in failures]

        snap = IdentitySnapshot(
            timestamp=datetime.now().isoformat(),
            wisdom_level=self.wisdom,
            skill_count=self.skill_count(),
            goal_count=len(goals),
            failure_patterns=failure_patterns,
            strengths=strengths,
            self_description=self_description
        )

        # Save snapshot
        try:
            with sqlite3.connect(self.db) as c:
                c.execute("""
                    INSERT INTO identity
                    (timestamp, wisdom_level, skill_count, goal_count,
                     failure_patterns, strengths, self_description)
                    VALUES (?,?,?,?,?,?,?)
                """, (snap.timestamp, snap.wisdom_level, snap.skill_count,
                      snap.goal_count, json.dumps(snap.failure_patterns),
                      json.dumps(snap.strengths), snap.self_description))
        except Exception as e:
            logger.error("Failed to save identity snapshot: %s", e)
            raise

        return snap

    # ─────────────────────────────────────────────
    # STATUS REPORT
    # ─────────────────────────────────────────────

    def status(self) -> Dict:
        return {
            "wisdom":        round(self.wisdom, 4),
            "skills":        self.skill_count(),
            "active_goals":  self.active_goal_count(),
            "failures":      len(self.get_failure_patterns()),
            "best_skills":   [s['name'] for s in self.get_best_skills(3)],
        }

    def print_status(self) -> None:
        """Print the current status of the self graph.

        Retrieves and displays the current wisdom, skills, active goals,
        failure patterns, and best skills in a formatted output.

        Args:
            None

        Returns:
            None

        Raises:
            Exception: If an error occurs while retrieving or printing status.
                       The exception is logged before being re-raised.
        """
        from logger import setup_logger
        logger = setup_logger(__name__)
        try:
            logger.info("print_status called")
            s = self.status()
            logger.debug(f"status retrieved: wisdom={s['wisdom']:.4f}, skills={s['skills']}, active_goals={s['active_goals']}, failures={s['failures']}, best_skills={s['best_skills']}")
            print("\n" + "─"*45)
            print("🧬 SELF GRAPH STATUS")
            print("─"*45)
            print(f"  ਬੁੱਧੀ ਪੱਧਰ:    {s['wisdom']:.4f}")
            print(f"  ਸਕਿੱਲਾਂ:       {s['skills']}")
            print(f"  ਸਰਗਰਮ ਟੀਚੇ:   {s['active_goals']}")
            print(f"  ਅਸਫ਼ਲਤਾ ਪੈਟਰਨ: {s['failures']}")
            print(f"  ਚੋਟੀ ਦੀਆਂ:    {', '.join(s['best_skills'])}")
            print("─"*45)
            logger.debug("Status printed successfully")
        except Exception as e:
            logger.error(f"Error in print_status: {e}")
            raise


# ══════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sg = SelfGraph()

    # ਕੁਝ skills ਸਿੱਖੋ
    sg.learn_skill("web_search", "DuckDuckGo ਤੋਂ ਜਾਣਕਾਰੀ ਲੈਣਾ", "research")
    sg.learn_skill("code_gen",   "Python code ਬਣਾਉਣਾ",          "coding")
    sg.learn_skill("reasoning",  "Chain-of-thought ਸੋਚ",         "reasoning")

    # Skill ਕਾਮਯਾਬ/ਅਸਫ਼ਲ
    sg.skill_succeeded("web_search")
    sg.skill_succeeded("web_search")
    sg.skill_failed("code_gen")

    # ਟੀਚਾ ਰੱਖੋ
    sg.set_goal("Amrit Research Field ਪੂਰਾ ਕਰੋ", priority=0.9)
    sg.set_goal("Hypervector memory ਜੋੜੋ",        priority=0.7)

    # ਅਸਫ਼ਲਤਾ ਰਿਕਾਰਡ
    sg.record_failure("Ollama timeout on large prompts",
                      context="research module", module="llm_client")

    # ਸਥਿਤੀ
    sg.print_status()

    # ਸਵੈ-ਚਿੰਤਨ
    print("\n🪞 ਸਵੈ-ਚਿੰਤਨ ਕਰ ਰਹੇ ਹਾਂ...")
    snap = sg.reflect()
    print(f"\n💭 ਅਮ੍ਰਿਤ ਬਾਰੇ ਅਮ੍ਰਿਤ:\n   {snap.self_description}")