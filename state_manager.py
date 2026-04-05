"""State Manager — Namespaced, persistent, watchable global state."""
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Optional
from logger import setup_logger

logger = setup_logger("StateManager")

class StateManager:
    def __init__(self, persist_path: str = "workspace/state.json"):
        self._state   = {}
        self._history = []
        self._path    = Path(persist_path)
        self._lock    = asyncio.Lock()
        self._watchers: dict[str, list] = {}
        self.load()

    async def set(self, key: str, value: Any, ns: str = "global"):
        fk = f"{ns}:{key}"
        async with self._lock:
            old = self._state.get(fk)
            self._state[fk] = value
            self._history.append({"k": fk, "old": old, "new": value,
                                   "t": datetime.now().isoformat()})
            if len(self._history) > 2000:
                self._history = self._history[-2000:]
        await self._notify(fk, old, value)

    def get(self, key: str, default: Any = None, ns: str = "global") -> Any:
        return self._state.get(f"{ns}:{key}", default)

    async def delete(self, key: str, ns: str = "global"):
        async with self._lock:
            self._state.pop(f"{ns}:{key}", None)

    def ns(self, namespace: str) -> dict:
        prefix = f"{namespace}:"
        return {k[len(prefix):]: v for k, v in self._state.items()
                if k.startswith(prefix)}

    def watch(self, key: str, cb, ns: str = "global"):
        self._watchers.setdefault(f"{ns}:{key}", []).append(cb)

    async def _notify(self, fk, old, new):
        for cb in self._watchers.get(fk, []):
            try:
                await cb(old, new) if asyncio.iscoroutinefunction(cb) else cb(old, new)
            except Exception as e:
                logger.error(f"Watcher error: {e}")

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    def load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._state = json.load(f)
                logger.info(f"State loaded: {len(self._state)} keys")
            except Exception as e:
                logger.warning(f"State load error: {e}")

    def snapshot(self) -> dict:
        return dict(self._state)

    def history(self, limit=50) -> list:
        return self._history[-limit:]
