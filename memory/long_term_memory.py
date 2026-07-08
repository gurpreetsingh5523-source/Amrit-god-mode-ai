"""
Long-Term Memory — SQLite-backed persistent memory.
Survives crashes, supports fast search, tags, and multi-session recall.
Falls back to JSON if SQLite unavailable.
"""
import json
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("LongTermMemory")

DB_PATH = Path("workspace/memory.db")
JSON_PATH = Path("workspace/memory.json")


class LongTermMemory:
    """
    Persistent key-value memory with tags, search, and SQLite backend.
    Automatically migrates existing JSON memory to SQLite on first run.
    """

    def __init__(self, path: str = None):
        self._use_sqlite = False
        self._data = {}   # in-memory cache + JSON fallback
        self._meta = {}
        self._db_path = Path(path).with_suffix(".db") if path else DB_PATH
        self._json_path = JSON_PATH
        self._init_storage()

    def _init_storage(self):
        """Initialize SQLite, migrating from JSON if needed."""
        try:
            import sqlite3
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_updated ON memory(updated_at)")
            conn.commit()
            conn.close()
            self._use_sqlite = True
            logger.info(f"SQLite memory: {self._db_path}")
            self._migrate_from_json()
        except Exception as e:
            logger.warning(f"SQLite unavailable ({e}), using JSON fallback")
            self._load_json()

    def _migrate_from_json(self):
        """One-time migration: JSON → SQLite."""
        if not self._json_path.exists():
            return
        try:
            data = json.loads(self._json_path.read_text())
            entries = data.get("data", {})
            metas = data.get("meta", {})
            if not entries:
                return
            import sqlite3
            conn = sqlite3.connect(str(self._db_path))
            migrated = 0
            for key, value in entries.items():
                m = metas.get(key, {})
                conn.execute(
                    "INSERT OR IGNORE INTO memory VALUES (?,?,?,?,?)",
                    (key, json.dumps(value, default=str),
                     json.dumps(m.get("tags", [])),
                     m.get("created", datetime.now().isoformat()),
                     m.get("updated", datetime.now().isoformat()))
                )
                migrated += 1
            conn.commit()
            conn.close()
            if migrated:
                logger.info(f"Migrated {migrated} entries from JSON to SQLite")
                self._json_path.rename(self._json_path.with_suffix(".json.bak"))
        except Exception as e:
            logger.warning(f"Migration failed: {e}")

    # ── Core API ──────────────────────────────────────────────

    def remember(self, key: str, value, tags=None):
        """Store a memory entry."""
        now = datetime.now().isoformat()
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                existing = conn.execute(
                    "SELECT created_at FROM memory WHERE key=?", (key,)
                ).fetchone()
                created = existing[0] if existing else now
                conn.execute(
                    "INSERT OR REPLACE INTO memory VALUES (?,?,?,?,?)",
                    (key, json.dumps(value, default=str),
                     json.dumps(tags or []), created, now)
                )
                conn.commit()
                conn.close()
                return
            except Exception as e:
                logger.warning(f"SQLite write failed: {e} — using cache")

        # JSON fallback
        self._data[key] = value
        self._meta[key] = {
            "updated": now,
            "created": self._meta.get(key, {}).get("created", now),
            "tags": tags or []
        }
        self.save()

    def recall(self, key: str, default=None):
        """Retrieve a memory entry by key."""
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                row = conn.execute(
                    "SELECT value FROM memory WHERE key=?", (key,)
                ).fetchone()
                conn.close()
                if row:
                    return json.loads(row[0])
                return default
            except Exception:
                pass
        return self._data.get(key, default)

    def forget(self, key: str):
        """Delete a memory entry."""
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                conn.execute("DELETE FROM memory WHERE key=?", (key,))
                conn.commit()
                conn.close()
                return
            except Exception:
                pass
        self._data.pop(key, None)
        self._meta.pop(key, None)
        self.save()

    def search(self, q: str, limit: int = 20) -> dict:
        """Full-text search across keys and values."""
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                rows = conn.execute(
                    "SELECT key, value FROM memory WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                    (f"%{q}%", f"%{q}%", limit)
                ).fetchall()
                conn.close()
                return {r[0]: json.loads(r[1]) for r in rows}
            except Exception:
                pass
        return {k: v for k, v in self._data.items()
                if q.lower() in k.lower() or q.lower() in str(v).lower()}

    def by_tag(self, tag: str) -> dict:
        """Retrieve all entries with a specific tag."""
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                rows = conn.execute(
                    "SELECT key, value FROM memory WHERE tags LIKE ?",
                    (f'%"{tag}"%',)
                ).fetchall()
                conn.close()
                return {r[0]: json.loads(r[1]) for r in rows}
            except Exception:
                pass
        return {k: self._data[k] for k, m in self._meta.items()
                if tag in m.get("tags", [])}

    def keys(self) -> list:
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                rows = conn.execute("SELECT key FROM memory ORDER BY updated_at DESC").fetchall()
                conn.close()
                return [r[0] for r in rows]
            except Exception:
                pass
        return list(self._data.keys())

    def recent(self, n: int = 10) -> list:
        """Return most recently updated entries."""
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                rows = conn.execute(
                    "SELECT key, value, updated_at FROM memory ORDER BY updated_at DESC LIMIT ?", (n,)
                ).fetchall()
                conn.close()
                return [{"key": r[0], "value": json.loads(r[1]), "updated": r[2]} for r in rows]
            except Exception:
                pass
        items = sorted(self._meta.items(), key=lambda x: x[1].get("updated", ""), reverse=True)
        return [{"key": k, "value": self._data.get(k), "updated": m.get("updated")}
                for k, m in items[:n]]

    def stats(self) -> dict:
        if self._use_sqlite:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self._db_path))
                count = conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
                conn.close()
                return {"total_entries": count, "backend": "sqlite", "path": str(self._db_path)}
            except Exception:
                pass
        return {"total_entries": len(self._data), "backend": "json", "path": str(self._json_path)}

    # ── JSON fallback persistence ─────────────────────────────

    def save(self):
        """Save to JSON (only used as fallback when SQLite unavailable)."""
        if self._use_sqlite:
            return
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._json_path, "w") as f:
            json.dump({"data": self._data, "meta": self._meta}, f, indent=2, default=str)

    def _load_json(self):
        if self._json_path.exists():
            try:
                p = json.loads(self._json_path.read_text())
                self._data = p.get("data", {})
                self._meta = p.get("meta", {})
                logger.info(f"JSON memory loaded: {len(self._data)} entries")
            except Exception as e:
                logger.warning(f"JSON load error: {e}")
