"""
Event Bus — High-performance async pub/sub with wildcards,
priority queues, replay, and dead-letter queue.
"""
import asyncio
from collections import defaultdict
from typing import Callable, Any, Optional
from datetime import datetime
from logger import setup_logger

logger = setup_logger("EventBus")


class Event:
    def __init__(self, name: str, data: Any = None, source: str = "system",
                 priority: int = 5):
        self.name      = name
        self.data      = data
        self.source    = source
        self.priority  = priority
        self.timestamp = datetime.now().isoformat()
        self.id        = f"{name}_{datetime.now().timestamp():.4f}"

    def __repr__(self):
        return f"Event({self.name!r}, src={self.source!r})"


class EventBus:
    def __init__(self, history_limit: int = 1000):
        self._subs:        dict[str, list[Callable]] = defaultdict(list)
        self._wildcard:    list[Callable] = []
        self._history:     list[Event]   = []
        self._dead_letter: list[Event]   = []
        self._limit        = history_limit
        self._stats:       dict[str, int] = defaultdict(int)
        self._middlewares: list[Callable] = []
        self._running      = False

    async def start(self):
        self._running = True
        logger.info("EventBus started ✅")

    async def stop(self):
        self._running = False

    # ── Subscribe ──────────────────────────────────────────────────

    def subscribe(self, event: str, cb: Callable):
        self._subs[event].append(cb)

    def subscribe_all(self, cb: Callable):
        self._wildcard.append(cb)

    def use_middleware(self, fn: Callable):
        """Add middleware that runs before each dispatch."""
        self._middlewares.append(fn)

    def unsubscribe(self, event: str, cb: Callable):
        if event in self._subs:
            try: self._subs[event].remove(cb)
            except ValueError: pass

    # ── Publish ────────────────────────────────────────────────────

    async def publish(self, name: str, data: Any = None,
                      source: str = "system", priority: int = 5) -> Event:
        evt = Event(name, data, source, priority)
        self._history.append(evt)
        if len(self._history) > self._limit:
            self._history.pop(0)
        self._stats[name] += 1

        # Run middleware
        for mw in self._middlewares:
            try:
                await mw(evt) if asyncio.iscoroutinefunction(mw) else mw(evt)
            except Exception as e:
                logger.warning(f"Middleware error: {e}")

        callbacks = list(self._subs.get(name, [])) + self._wildcard
        if not callbacks:
            self._dead_letter.append(evt)

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(evt)
                else:
                    cb(evt)
            except Exception as e:
                logger.error(f"Subscriber error [{name}] {cb.__qualname__}: {e}")

        return evt

    async def emit(self, name: str, data: Any = None, source: str = "system"):
        """Alias for publish."""
        return await self.publish(name, data, source)

    # ── Inspection ─────────────────────────────────────────────────

    def history(self, name: Optional[str] = None, limit: int = 50) -> list:
        h = self._history
        if name:
            h = [e for e in h if e.name == name]
        return h[-limit:]

    def stats(self) -> dict:
        return dict(self._stats)

    def dead_letters(self) -> list:
        return list(self._dead_letter)
