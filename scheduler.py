"""Scheduler — Time-based and recurring task scheduling."""
import asyncio
from datetime import datetime
from logger import setup_logger

logger = setup_logger("Scheduler")


class Scheduler:
    def __init__(self, task_graph):
        self.graph   = task_graph
        self._jobs   = {}
        self._ctr    = 0
        self._handles= []

    def _id(self):
        self._ctr += 1
        return f"job_{self._ctr}"

    async def schedule_at(self, task: dict, run_at: datetime) -> str:
        delay = (run_at - datetime.now()).total_seconds()
        jid = self._id()
        async def _run():
            if delay > 0: await asyncio.sleep(delay)
            self.graph.add(task)
            logger.info(f"[{jid}] Triggered at {run_at}")
        self._handles.append(asyncio.create_task(_run()))
        return jid

    async def schedule_after(self, task: dict, seconds: float) -> str:
        jid = self._id()
        async def _run():
            await asyncio.sleep(seconds)
            self.graph.add(task)
            logger.info(f"[{jid}] Triggered after {seconds}s")
        self._handles.append(asyncio.create_task(_run()))
        return jid

    async def schedule_recurring(self, task: dict, interval: float,
                                  times: int = -1) -> str:
        jid  = self._id()
        info = {"active": True, "count": 0}
        self._jobs[jid] = info
        async def _run():
            while info["active"] and (times == -1 or info["count"] < times):
                self.graph.add(dict(task))
                info["count"] += 1
                logger.info(f"[{jid}] Recurring fire #{info['count']}")
                await asyncio.sleep(interval)
        self._handles.append(asyncio.create_task(_run()))
        return jid

    def cancel(self, jid: str):
        if jid in self._jobs:
            self._jobs[jid]["active"] = False

    def cancel_all(self):
        for info in self._jobs.values():
            info["active"] = False
        for h in self._handles:
            h.cancel()
