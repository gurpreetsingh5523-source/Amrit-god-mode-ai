"""
Autonomy Loop — The heartbeat of GODMODE.
Executes tasks from the graph, handles parallelism, retries, and self-learning.
"""
import asyncio
import time
from task_graph import TaskStatus
from logger import setup_logger
from ethical_guard import EthicalGuard

logger = setup_logger("AutonomyLoop")




class AutonomyLoop:
    def __init__(self, orchestrator, max_iterations: int = 500):
        self.orc            = orchestrator
        self.max_iterations = max_iterations
        self.running        = False
        self._iter          = 0
        self._t0            = None
        self.parallel       = True
        self.max_retries    = 2
        self._retry_counts  = {}   # task_id → retry count
        # Central EthicalGuard for silent enforcement across all agents/tasks
        self.guard = EthicalGuard()

    async def run(self, strategy: str = "auto"):
        self.running = True
        self._iter   = 0
        self._t0     = time.time()
        graph        = self.orc.task_graph

        logger.info(f"Autonomy loop started | strategy={strategy}")

        while self.running and self._iter < self.max_iterations:
            if graph.is_complete():
                logger.info("All tasks complete ✅")
                break

            ready = graph.get_ready()
            if not ready:
                if graph.has_pending():
                    await asyncio.sleep(0.2)
                    continue
                break

            self._iter += 1
            elapsed = time.time() - self._t0

            if self.parallel and len(ready) > 1:
                logger.info(f"[Iter {self._iter}] Running {len(ready)} tasks in parallel | {elapsed:.1f}s elapsed")
                await asyncio.gather(*[self._execute(t) for t in ready])
            else:
                task = ready[0]
                logger.info(f"[Iter {self._iter}] '{task.name}' → {task.agent} | {elapsed:.1f}s")
                await self._execute(task)

        self.running = False
        elapsed = time.time() - self._t0
        s = graph.summary()
        logger.info(f"Loop done in {elapsed:.2f}s | {s}")

        # Trigger learning from experience
        await self._learn()

    async def _execute(self, task):
        graph  = self.orc.task_graph

        task.mark_running()
        # Central EthicalGuard check: silently block unsafe tasks before execution
        try:
            desc = f"{task.agent} {task.name} {task.to_dict().get('data','')}"
            safe, reason = self.guard.check(desc)
            if not safe:
                result = {"agent": task.agent,
                          "status": "error",
                          "error": f"Action FAILED: Blocked by EthicalGuard because {reason}. Find a safer alternative."}
                task.mark_done(result)
                await self.orc.event_bus.publish("task.complete",
                    {"id": task.id, "name": task.name, "result": result}, source=task.agent)
                logger.warning(f"Task '{task.name}' blocked by EthicalGuard: {reason}")
                return

            # Try get_or_create_agent if orchestrator supports it
            if hasattr(self.orc, 'get_or_create_agent'):
                agent = await self.orc.get_or_create_agent(task.agent, task.to_dict().get('data'))
            else:
                agent = self.orc.get_agent(task.agent)
            if not agent:
                agent = self.orc.get_agent("planner")
            if not agent:
                task.mark_failed("No agent available")
                return

            result = await asyncio.wait_for(agent.execute(task.to_dict()), timeout=task.timeout)
            task.mark_done(result)
            await self.orc.event_bus.publish("task.complete",
                {"id": task.id, "name": task.name, "result": result}, source=task.agent)
        except asyncio.TimeoutError:
            retries = self._retry_counts.get(task.id, 0)
            if retries < self.max_retries:
                self._retry_counts[task.id] = retries + 1
                logger.warning(f"Task '{task.name}' timed out — retry {retries+1}/{self.max_retries}")
                task.status = TaskStatus.PENDING  # reset for retry
            else:
                task.mark_failed("Timeout after retries")
                logger.error(f"Task '{task.name}' timed out after {self.max_retries} retries")
        except Exception as e:
            retries = self._retry_counts.get(task.id, 0)
            if retries < self.max_retries:
                self._retry_counts[task.id] = retries + 1
                logger.warning(f"Task '{task.name}' error: {e} — retry {retries+1}/{self.max_retries}")
                task.status = TaskStatus.PENDING  # reset for retry
            else:
                task.mark_failed(str(e))
                logger.error(f"Task '{task.name}' failed after {self.max_retries} retries: {e}")
                await self.orc.event_bus.publish("agent.error",
                    {"agent": task.agent, "task": task.name, "error": str(e)})

    async def _learn(self):
        try:
            learner = self.orc.get_agent("upgrade")
            if learner:
                await learner.execute({"name": "post-run learning",
                                        "data": {"action": "analyze"}})
        except Exception:
            pass

    def stop(self):
        self.running = False
