#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║  🌙 dream_engine.py — ਸੁਪਨੇ ਦਾ ਇੰਜਣ                ║
║                                                      ║
║  "Biological sleep consolidation ਵਰਗਾ"               ║
║                                                      ║
║  Idle ਹੋਣ ਤੇ:                                        ║
║    • ਪੁਰਾਣੀਆਂ discoveries ਮਿਲਾਓ                     ║
║    • ਅਣਜੁੜੇ ideas ਜੋੜੋ                              ║
║    • Failed attempts retry ਕਰੋ                       ║
║    • Symbolic mutation ਕਰੋ                           ║
║    • ਨਵੀਆਂ hypotheses ਜਨਮ ਲੈਣ                       ║
╚══════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import random
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from config import CFG
from llm_client import LLMClient


class DreamEngine:
	"""
	System ਜਦੋਂ idle ਹੋਵੇ — ਸੁਪਨੇ ਵੇਖਦਾ ਹੈ।
	Corporate AI ਇਹ ਨਹੀਂ ਕਰਦੇ।
	ਉਹ inference machines ਹਨ।
	ਅਮ੍ਰਿਤ ਵੱਖਰਾ ਹੈ।
	"""

	def __init__(self):
		self.db = CFG.memory_dir / "dreams.db"
		self.dreams_dir = CFG.dreams_dir
		self.llm = LLMClient(system_prompt=
			"You are the creative dream engine of Amrit AI. "
			"You recombine ideas in unexpected, insightful ways. "
			"Be creative, specific, and generate genuine new insights. "
			"2-3 sentences maximum per dream fragment.")
		self._init_db()
		print("🌙 DreamEngine — ਸੁਪਨੇ ਦਾ ਦਰਵਾਜ਼ਾ ਖੁੱਲ੍ਹਿਆ")

	def _init_db(self):
		with sqlite3.connect(self.db) as c:
			c.executescript("""
			CREATE TABLE IF NOT EXISTS dream_sources (
				id TEXT PRIMARY KEY,
				topic TEXT,
				content TEXT,
				source_type TEXT,   -- "discovery"|"skill"|"failure"|"goal"
				added TEXT
			);

			CREATE TABLE IF NOT EXISTS dreams (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				dream_type TEXT,
				source_ids TEXT,    -- JSON list
				content TEXT NOT NULL,
				insight TEXT,
				novelty_score REAL DEFAULT 0.5,
				timestamp TEXT,
				saved_file TEXT
			);
			""")

	# ─────────────────────────────────────────────
	# FEED DREAM SOURCES
	# ─────────────────────────────────────────────

	def feed(self, topic: str, content: str,
			 source_type: str = "discovery") -> str:
		"""ਸੁਪਨਿਆਂ ਲਈ ਸਮੱਗਰੀ ਦਿਓ"""
		sid = hashlib.sha256(f"{topic}{content[:50]}".encode()).hexdigest()[:10]
		with sqlite3.connect(self.db) as c:
			c.execute("""
				INSERT OR REPLACE INTO dream_sources
				(id, topic, content, source_type, added)
				VALUES (?,?,?,?,?)
			""", (sid, topic, content[:500], source_type,
				  datetime.now().isoformat()))
		return sid

	def _get_sources(self, n: int = 4) -> List[Dict]:
		"""ਸੁਪਨੇ ਲਈ ਸਮੱਗਰੀ ਲਵੋ"""
		with sqlite3.connect(self.db) as c:
			c.row_factory = sqlite3.Row
			rows = c.execute("""
				SELECT * FROM dream_sources
				ORDER BY RANDOM() LIMIT ?
			""", (n,)).fetchall()
			return [dict(r) for r in rows]

	def _source_count(self) -> int:
		with sqlite3.connect(self.db) as c:
			return c.execute("SELECT COUNT(*) FROM dream_sources").fetchone()[0]

	# ─────────────────────────────────────────────
	# DREAM TYPES
	# ─────────────────────────────────────────────

	def _dream_fusion(self, sources: List[Dict]) -> str:
		"""ਦੋ ਅਣਜੁੜੇ ideas ਨੂੰ ਮਿਲਾਓ"""
		if len(sources) < 2:
			return "ਕਾਫ਼ੀ ਸਮੱਗਰੀ ਨਹੀਂ"
		s1, s2 = random.sample(sources, 2)
		prompt = f"""Dream Fusion Task:

Idea A: "{s1['topic']}" — {s1['content'][:200]}
Idea B: "{s2['topic']}" — {s2['content'][:200]}

These seem unrelated. Find a DEEP, SPECIFIC, SURPRISING connection.
What emerges when you fuse these two ideas?
Generate a new concept or hypothesis from this fusion."""

		return self.llm.ask(prompt)

	def _dream_mutation(self, sources: List[Dict]) -> str:
		"""ਇੱਕ idea ਨੂੰ ਬਦਲੋ — symbolic mutation"""
		if not sources:
			return "ਕਾਫ਼ੀ ਸਮੱਗਰੀ ਨਹੀਂ"
		source = random.choice(sources)
		mutations = [
			"invert it completely",
			"apply it to the opposite domain",
			"make it 10x smaller or larger",
			"combine it with its own opposite",
			"view it through Gurbani philosophy"
		]
		mutation = random.choice(mutations)
		prompt = f"""Dream Mutation Task:

Original concept: "{source['topic']}" — {source['content'][:250]}

Mutation instruction: {mutation}

What new insight or direction emerges?
Be specific and practical."""

		return self.llm.ask(prompt)

	def _dream_retry_failure(self, sources: List[Dict]) -> str:
		"""ਅਸਫ਼ਲ ਕੋਸ਼ਿਸ਼ਾਂ ਨੂੰ ਨਵੇਂ ਨਜ਼ਰੀਏ ਤੋਂ"""
		failures = [s for s in sources if s['source_type'] == 'failure']
		if not failures:
			return self._dream_fusion(sources)

		failure = random.choice(failures)
		prompt = f"""Dream Recovery Task:

Failed attempt: "{failure['topic']}"
Context: {failure['content'][:250]}

In this dream state, approach it fresh:
1. What assumption was wrong?
2. What's a completely different approach?
3. What would success look like?"""

		return self.llm.ask(prompt)

	def _dream_cross_domain(self, sources: List[Dict]) -> str:
		"""ਵੱਖ-ਵੱਖ domains ਤੋਂ ideas ਇਕੱਠੇ"""
		if len(sources) < 3:
			return self._dream_fusion(sources)

		selected = random.sample(sources, min(3, len(sources)))
		ideas = "\n".join([
			f"• [{s['source_type']}] {s['topic']}: {s['content'][:100]}"
			for s in selected
		])
		prompt = f"""Cross-Domain Dream Synthesis:

Multiple fragments from different domains:
{ideas}

Find a unified principle or pattern that connects all of them.
This is a creative synthesis — not just a list.
What emerges when all three collide?"""

		return self.llm.ask(prompt)

	# ─────────────────────────────────────────────
	# MAIN DREAM FUNCTION
	# ─────────────────────────────────────────────

	def dream(self) -> Optional[Dict]:
		"""
		ਇੱਕ ਸੁਪਨਾ — ਸਭ ਤੋਂ ਮਹੱਤਵਪੂਰਨ function

		Returns dream dict or None if not enough sources
		"""
		count = self._source_count()
		if count < 2:
			print("🌙 ਸੁਪਨੇ ਲਈ ਕਾਫ਼ੀ ਯਾਦਾਂ ਨਹੀਂ — feed() ਕਰੋ ਪਹਿਲਾਂ")
			return None

		sources = self._get_sources(CFG.dream_batch + 2)

		# ਸੁਪਨੇ ਦੀ ਕਿਸਮ ਚੁਣੋ
		dream_types = {
			"fusion":       self._dream_fusion,
			"mutation":     self._dream_mutation,
			"retry":        self._dream_retry_failure,
			"cross_domain": self._dream_cross_domain,
		}

		dream_type = random.choice(list(dream_types.keys()))
		dream_fn = dream_types[dream_type]

		print(f"\n🌙 ਸੁਪਨਾ [{dream_type}] ਸ਼ੁਰੂ...")
		content = dream_fn(sources)

		# Novelty score (ਸਾਧਾਰਨ ਅੰਦਾਜ਼ਾ — ਲੰਮਾ = ਜ਼ਿਆਦਾ novel)
		novelty = min(1.0, len(content.split()) / 100.0)

		source_ids = [s['id'] for s in sources]

		# Save
		with sqlite3.connect(self.db) as c:
			cursor = c.cursor()
			cursor.execute("""
				INSERT INTO dreams
				(dream_type, source_ids, content, novelty_score, timestamp)
				VALUES (?,?,?,?,?)
			""", (dream_type, json.dumps(source_ids),
				  content, novelty, datetime.now().isoformat()))
			dream_id = cursor.lastrowid
			c.commit()

		# File ਵਿੱਚ ਸੰਭਾਲੋ
		dream_file = self.dreams_dir / f"dream_{dream_id}_{dream_type}.txt"
		dream_file.write_text(
			f"🌙 AMRIT DREAM — {dream_type}\n"
			f"ਸਮਾਂ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
			f"Sources: {len(sources)}\n"
			f"{'─'*50}\n\n"
			f"{content}\n\n"
			f"{'─'*50}\n"
			f"Novelty: {novelty:.3f}\n",
			encoding="utf-8"
		)

		dream = {
			"id":       dream_id,
			"type":     dream_type,
			"content":  content,
			"novelty":  novelty,
			"file":     str(dream_file),
			"sources":  len(sources)
		}

		print(f"✨ ਸੁਪਨਾ ਸੰਭਲਿਆ: {dream_file.name}")
		print(f"   Novelty: {novelty:.3f}")
		print(f"\n💭 {content[:200]}...")

		return dream

	def dream_batch(self, n: int = 3) -> List[Dict]:
		"""ਕਈ ਸੁਪਨੇ ਇੱਕੋ ਵਾਰ"""
		print(f"\n🌙 ਸੁਪਨਿਆਂ ਦੀ ਰਾਤ — {n} ਸੁਪਨੇ...")
		results = []
		for i in range(n):
			print(f"\n[{i+1}/{n}]", end=" ")
			dream = self.dream()
			if dream:
				results.append(dream)
			time.sleep(1)
		return results

	def get_recent_dreams(self, limit: int = 5) -> List[Dict]:
		"""ਤਾਜ਼ੇ ਸੁਪਨੇ"""
		with sqlite3.connect(self.db) as c:
			c.row_factory = sqlite3.Row
			rows = c.execute("""
				SELECT * FROM dreams
				ORDER BY id DESC LIMIT ?
			""", (limit,)).fetchall()
			return [dict(r) for r in rows]

	def status(self) -> Dict:
		with sqlite3.connect(self.db) as c:
			sources = c.execute("SELECT COUNT(*) FROM dream_sources").fetchone()[0]
			total   = c.execute("SELECT COUNT(*) FROM dreams").fetchone()[0]
			avg_nov = c.execute(
				"SELECT AVG(novelty_score) FROM dreams"
			).fetchone()[0] or 0
		return {
			"dream_sources": sources,
			"total_dreams":  total,
			"avg_novelty":   round(avg_nov, 3),
			"dreams_dir":    str(self.dreams_dir)
		}


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
	de = DreamEngine()

	# ਕੁਝ ਸਮੱਗਰੀ ਦਿਓ
	de.feed("quantum consciousness",
			"Consciousness may emerge from quantum processes in microtubules",
			"discovery")
	de.feed("Gurbani Naam vibration",
			"Naam repetition creates rhythmic neural patterns — similar to meditation",
			"discovery")
	de.feed("Punjabi music raag therapy",
			"Raag Bhairav reduces cortisol — morning raga with healing properties",
			"discovery")
	de.feed("Failed web scraping",
			"DuckDuckGo blocking requests after 3 rapid calls",
			"failure")

	# ਸੁਪਨਾ ਵੇਖੋ
	dream = de.dream()

	print("\n📊 STATUS:", de.status())