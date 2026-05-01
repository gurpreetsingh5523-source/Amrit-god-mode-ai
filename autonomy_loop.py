"""
Autonomy Loop — The heartbeat of GODMODE.
Executes tasks from the graph, handles parallelism, retries, and self-learning.
"""

# ✅ ਸਾਰੇ imports ਹੁਣ docstring ਤੋਂ ਬਾਅਦ — E402 ਖ਼ਤਮ
import asyncio
import re
import time

from ethical_guard import EthicalGuard
from logger import setup_logger
from meta_cognition import MetaCognition
from task_graph import TaskStatus

logger = setup_logger("AutonomyLoop")


class AutonomyLoop:
    def __init__(self, orchestrator, max_iterations: int = 500):
        logger.info(
            "Initialized with orchestrator={} and max_iterations={}".format(
                orchestrator, max_iterations
            )
        )
        logger.debug("Setting max_iterations from param: {}".format(max_iterations))
        self.orc = orchestrator
        self.max_iterations = max_iterations
        self.running = False
        self._iter = 0
        self._t0 = None
        self.parallel = True
        self.max_retries = 2
        self._retry_counts = {}  # task_id → retry count
        try:
            self.guard = EthicalGuard()
            logger.debug("Initialized guard successfully.")
            self.meta = MetaCognition()
            logger.debug("Initialized meta successfully.")
        except Exception as e:
            logger.error("Error occurred during init: {}".format(str(e)))
        self._performance_log = []

    async def run(self, strategy: str = "auto"):
        """
        Main loop for autonomous task execution.
        Handles parallelism, retries, meta-cognition, and policy updates.
        """
        self.running = True
        self._iter = 0
        self._t0 = time.time()
        graph = self.orc.task_graph

        logger.info(f"Autonomy loop started | strategy={strategy}")
        current_strategy = strategy

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

            self._handle_meta_and_policy(elapsed, current_strategy)
            current_strategy = self._get_current_strategy()

            if self.parallel and len(ready) > 1:
                logger.info(
                    f"[Iter {self._iter}] Running {len(ready)} tasks in parallel | {elapsed:.1f}s elapsed"
                )
                await asyncio.gather(*[self._execute(t) for t in ready])
            else:
                task = ready[0]
                logger.info(
                    f"[Iter {self._iter}] '{task.name}' → {task.agent} | {elapsed:.1f}s"
                )
                await self._execute(task)

        self.running = False
        elapsed = time.time() - self._t0
        s = graph.summary()
        logger.info(f"Loop done in {elapsed:.2f}s | {s}")
        await self._learn()

    def _handle_meta_and_policy(self, elapsed, current_strategy):
        """MetaCognition ਤੋਂ insights ਲਓ ਤੇ strategy ਬਦਲੋ ਜੇ ਲੋੜ ਹੋਵੇ।"""
        perf = self._collect_performance(elapsed)
        self._performance_log.append(perf)

        llm_fail_rate = self._get_llm_fail_rate()
        insights = self.meta.analyze_self(
            self._performance_log[-10:], perf, llm_fail_rate=llm_fail_rate
        )
        new_strategy = self.meta.decide_strategy(insights)
        if new_strategy != current_strategy:
            logger.info(
                f"[MetaCognition] Strategy changed: {current_strategy} → {new_strategy} (insights: {insights})"
            )
            self.max_retries = 4 if new_strategy == "increase_testing" else 2
            if hasattr(self.orc, "policy") and self.orc.policy:
                self._update_policy_from_insights(insights)
        self._current_strategy = new_strategy

    def _get_current_strategy(self):
        return getattr(self, "_current_strategy", "auto")

    def _get_llm_fail_rate(self):
        try:
            from llm_router import LLMRouter

            llm_router = getattr(self.orc, "llm_router", None)
            if llm_router is None:
                llm_router = LLMRouter()
            llm_stats = llm_router.get_stats()
            return llm_stats.get("errors", 0) / max(llm_stats.get("total", 1), 1)
        except Exception:
            return None

    def _collect_performance(self, elapsed):
        graph = self.orc.task_graph
        total = graph.total_tasks() if hasattr(graph, "total_tasks") else 1
        failed = graph.failed_tasks() if hasattr(graph, "failed_tasks") else 0
        failed_count = len(failed) if isinstance(failed, list) else failed
        fail_rate = failed_count / total if total else 0
        return {"fail_rate": fail_rate, "latency": elapsed}

    def _update_policy_from_insights(self, insights):
        from policy_engine import (
            ActionType,
            ConditionType,
            PolicyAction,
            PolicyCondition,
            PolicyRule,
        )

        for insight in insights:
            if "Too many failures" in insight:
                rule = PolicyRule(
                    name="auto_increase_testing_on_failures",
                    condition=PolicyCondition(
                        ctype=ConditionType.FAILURE_COUNT,
                        threshold=2,
                        window_seconds=60,
                    ),
                    action=PolicyAction(
                        action_type=ActionType.NOTIFY_USER,
                        description="Too many failures, increase testing",
                    ),
                    priority=2,
                )
                self.orc.policy.add_rule(rule)
            if "Slow thinking" in insight:
                rule = PolicyRule(
                    name="auto_optimize_model_on_latency",
                    condition=PolicyCondition(
                        ctype=ConditionType.TIME_ELAPSED, threshold=40
                    ),
                    action=PolicyAction(
                        action_type=ActionType.NOTIFY_USER,
                        description="High latency, optimize model usage",
                    ),
                    priority=2,
                )
                self.orc.policy.add_rule(rule)
            if insight == "llm_unstable":
                rule = PolicyRule(
                    name="reduce_llm_dependency_on_unstable",
                    condition=PolicyCondition(ctype=ConditionType.CUSTOM, threshold=1),
                    action=PolicyAction(
                        action_type=ActionType.NOTIFY_USER,
                        description="Reduce LLM dependency and optimize local execution",
                    ),
                    priority=2,
                )
                self.orc.policy.add_rule(rule)

    async def _execute(self, task):
        """ਇੱਕ task ਨੂੰ retries, ethical checks ਨਾਲ execute ਕਰੋ।"""
        logger.debug(f"[START] Executing task: {task.name} (agent={task.agent}, id={task.id})")
        task.mark_running()
        desc = f"{task.agent} {task.name} {task.to_dict().get('data', '')}"
        safe, reason = self.guard.check(desc)
        if not safe:
            result = {
                "agent": task.agent,
                "status": "error",
                "error": f"Action FAILED: Blocked by EthicalGuard because {reason}. Find a safer alternative.",
            }
            task.mark_done(result)
            await self.orc.event_bus.publish(
                "task.complete",
                {"id": task.id, "name": task.name, "result": result},
                source=task.agent,
            )
            logger.warning(f"Task '{task.name}' blocked by EthicalGuard: {reason}")
            return

        agent = await self._get_agent_for_task(task)
        if not agent:
            task.mark_failed("No agent available")
            logger.error(f"[FAILED] Task: {task.name} | No agent available")
            return

        heartbeat_task = asyncio.create_task(self._heartbeat())
        try:
            result = await self._execute_task_logic(task, agent)
        except asyncio.TimeoutError:
            await self.handle_timeout_error(task, heartbeat_task, retries=self._retry_counts.get(task.id, 0))
        except Exception as e:
            await self.handle_exception(task, heartbeat_task, e, self._retry_counts.get(task.id, 0))
        finally:
            asyncio.create_task(self._cancel_heartbeat(heartbeat_task))

    async def handle_timeout_error(self, task, heartbeat_task, retries):
        if retries < self.max_retries:
            self._retry_counts[task.id] = retries + 1
            logger.warning(f"Task '{task.name}' timed out — retry {retries + 1}/{self.max_retries}")
            task.status = TaskStatus.PENDING
        else:
            debugger = self.orc.get_agent("debugger")
            if debugger:
                await debugger.execute(
                    {"name": f"Debug: {task.name}", "data": {"error": "Timeout after retries", "task": task.to_dict()}}
                )
            task.mark_failed("Timeout after retries")
            logger.error(f"[FAILED] Task: {task.name} | Timed out after {self.max_retries} retries")

    async def handle_exception(self, task, heartbeat_task, exception, retries):
        if retries < self.max_retries:
            self._retry_counts[task.id] = retries + 1
            logger.warning(f"Task '{task.name}' error: {exception} — retry {retries + 1}/{self.max_retries}")
            task.status = TaskStatus.PENDING
        else:
            print(f"⚠️ [AMRIT] ਗਲਤੀ ਆਈ: {exception}\nਕਿਰਪਾ ਕਰਂ ਕੋਡ ਜਾਂ ਇੰਸਟਾਲੈਸ਼ਨ ਜਾਂਚੋ। (Swarm will continue)")
            debugger = self.orc.get_agent("debugger")
            if debugger:
                await debugger.execute(
                    {"name": f"Debug: {task.name}", "data": {"error": str(exception), "task": task.to_dict()}}
                )
            task.mark_failed(str(exception))
            logger.error(f"[FAILED] Task: {task.name} | Failed after {self.max_retries} retries: {exception}")
            await self.orc.event_bus.publish("agent.error", {"agent": task.agent, "task": task.name, "error": str(exception)})

    async def _cancel_heartbeat(self, heartbeat_task):
        if not heartbeat_task.done():
            heartbeat_task.cancel()

    async def _get_agent_for_task(self, task):
        if hasattr(self.orc, "get_or_create_agent"):
            agent = await self.orc.get_or_create_agent(
                task.agent, task.to_dict().get("data")
            )
        else:
            agent = self.orc.get_agent(task.agent)
        if not agent:
            agent = self.orc.get_agent("planner")
        return agent

    async def _heartbeat(self):
        start = time.time()
        while True:
            await asyncio.sleep(10)
            elapsed = int(time.time() - start)
            print(f"⏳ [AMRIT] ਕੰਮ ਚੱਲ ਰਿਹਾ ਹੈ... ਹੌਸਲਾ ਰੱਖੋ। (ਸਮਾਂ: {elapsed}s)")

    async def _execute_task_logic(self, task, agent):
        """Task ਦੀ ਕਿਸਮ ਦੇਖ ਕੇ ਸਹੀ execute ਕਰੋ।"""
        is_code_mod = False
        is_refactor = False
        if hasattr(task, "data") and isinstance(task.data, dict):
            action = task.data.get("action", "").lower()
            if action in {"patch", "modify_code", "apply_patch", "code_patch"}:
                is_code_mod = True
            if action == "refactor":
                is_refactor = True

        if is_code_mod and task.data.get("file") and task.data.get("new_code"):
            upgrade_agent = self.orc.get_agent("upgrade")
            tester_agent = self.orc.get_agent("tester")
            return await upgrade_agent.apply_patch_and_test(
                task.data["file"],
                task.data["new_code"],
                tester_agent,
                task_name=task.name,
            )
        if is_refactor:
            chunked_result = await self._chunked_refactor(task, chunk_size=40)
            if chunked_result:
                return chunked_result
        return await asyncio.wait_for(
            agent.execute(task.to_dict()), timeout=task.timeout
        )

    async def _chunked_refactor(self, task, chunk_size: int = 40):
        """ਵੱਡੇ ਫੰਕਸ਼ਨਾਂ ਨੂੰ chunks ਵਿੱਚ ਵੰਡ ਕੇ refactor ਕਰੋ।"""
        code = task.data.get("code") or task.data.get("new_code")
        if not code:
            return None
        line_count = code.count("\n")
        if line_count < chunk_size * 1.5:
            return None

        logger.info(
            f"[Chunked Refactor] {task.data.get('file', '?')} ({line_count} lines) → chunk_size={chunk_size}"
        )
        parts = re.split(r"^(def |class )", code, flags=re.MULTILINE)
        chunks = (
            [parts[i] + parts[i + 1] for i in range(1, len(parts), 2)]
            if len(parts) >= 3
            else [
                "\n".join(code.splitlines()[i : i + chunk_size])
                for i in range(0, line_count, chunk_size)
            ]
        )

        # ਛੋਟੇ chunks ਨੂੰ merge ਕਰੋ
        merged, buf = [], ""
        for chunk in chunks:
            if buf and (buf.count("\n") + chunk.count("\n")) < chunk_size:
                buf += "\n" + chunk
            else:
                if buf:
                    merged.append(buf)
                buf = chunk
        if buf:
            merged.append(buf)

        refactored_chunks = []
        for idx, chunk in enumerate(merged):
            subtask = task.to_dict().copy()
            subtask["data"] = {**task.data, "code": chunk, "new_code": chunk}
            logger.info(
                f"[Chunked Refactor] Chunk {idx + 1}/{len(merged)} ({len(chunk.splitlines())} lines)"
            )
            try:
                agent = self.orc.get_agent(task.agent)
                result = await asyncio.wait_for(
                    agent.execute(subtask), timeout=task.timeout
                )
                refactored_code = (
                    result.get("code") if isinstance(result, dict) else result
                )
                if not refactored_code or "invalid syntax" in str(refactored_code):
                    logger.warning(
                        f"[Chunked Refactor] Chunk {idx + 1} invalid — keeping original"
                    )
                    refactored_code = chunk
                refactored_chunks.append(refactored_code)
            except Exception as e:
                logger.error(
                    f"[Chunked Refactor] Chunk {idx + 1} exception: {e} — keeping original"
                )
                refactored_chunks.append(chunk)

        logger.info("[Chunked Refactor] Reassembling complete.")
        return {"code": "\n".join(refactored_chunks)}

    async def _learn(self):
        try:
            learner = self.orc.get_agent("upgrade")
            if learner:
                await learner.execute(
                    {"name": "post-run learning", "data": {"action": "analyze"}}
                )
        except Exception:
            pass

    def stop(self):
        self.running = False