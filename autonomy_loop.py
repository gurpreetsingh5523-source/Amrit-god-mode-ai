from meta_cognition import MetaCognition
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
        logger.info("Initialized with orchestrator={} and max_iterations={}".format(orchestrator, max_iterations))
        logger.debug("Setting max_iterations from param: {}".format(max_iterations))
        self.orc            = orchestrator
        self.max_iterations = max_iterations
        self.running        = False
        self._iter          = 0
        self._t0            = None
        self.parallel       = True
        self.max_retries    = 2
        self._retry_counts  = {}   # task_id → retry count
        try:
            self.guard = EthicalGuard()
            logger.debug("Initialized guard successfully.")
            self.meta = MetaCognition()
            logger.debug("Initialized meta successfully.")
        except Exception as e:
            logger.error("Error occurred during init: {}".format(str(e)))
        self._performance_log = []  # Store performance metrics for analysis


    async def run(self, strategy: str = "auto"):
        """
        Main loop for autonomous task execution. Handles parallelism, retries, meta-cognition, and policy updates.
        """
        self.running = True
        self._iter   = 0
        self._t0     = time.time()
        graph        = self.orc.task_graph

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

    def _handle_meta_and_policy(self, elapsed, current_strategy):
        """
        Collects performance, analyzes with MetaCognition, and updates policy if needed.
        """
        perf = self._collect_performance(elapsed)
        self._performance_log.append(perf)

        llm_fail_rate = self._get_llm_fail_rate()
        insights = self.meta.analyze_self(self._performance_log[-10:], perf, llm_fail_rate=llm_fail_rate)
        new_strategy = self.meta.decide_strategy(insights)
        if new_strategy != current_strategy:
            logger.info(f"[MetaCognition] Strategy changed: {current_strategy} → {new_strategy} (insights: {insights})")
            if new_strategy == "increase_testing":
                self.max_retries = 4
            else:
                self.max_retries = 2
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
        # Example: collect fail rate and latency
        graph = self.orc.task_graph
        total = graph.total_tasks() if hasattr(graph, 'total_tasks') else 1
        failed = graph.failed_tasks() if hasattr(graph, 'failed_tasks') else 0
        # If failed is a list, use its length
        if isinstance(failed, list):
            failed_count = len(failed)
        else:
            failed_count = failed
        fail_rate = failed_count / total if total else 0
        return {"fail_rate": fail_rate, "latency": elapsed}

    def _update_policy_from_insights(self, insights):
        # Example: add or update policy rules based on insights
        from policy_engine import PolicyCondition, ConditionType, PolicyAction, ActionType, PolicyRule
        for insight in insights:
            if "Too many failures" in insight:
                # Add or update a rule to increase testing or recovery
                rule = PolicyRule(
                    name="auto_increase_testing_on_failures",
                    condition=PolicyCondition(ctype=ConditionType.FAILURE_COUNT, threshold=2, window_seconds=60),
                    action=PolicyAction(action_type=ActionType.NOTIFY_USER, description="Too many failures, increase testing"),
                    priority=2
                )
                self.orc.policy.add_rule(rule)
            if "Slow thinking" in insight:
                rule = PolicyRule(
                    name="auto_optimize_model_on_latency",
                    condition=PolicyCondition(ctype=ConditionType.TIME_ELAPSED, threshold=40),
                    action=PolicyAction(action_type=ActionType.NOTIFY_USER, description="High latency, optimize model usage"),
                    priority=2
                )
                self.orc.policy.add_rule(rule)
            if insight == "llm_unstable":
                rule = PolicyRule(
                    name="reduce_llm_dependency_on_unstable",
                    condition=PolicyCondition(ctype=ConditionType.CUSTOM, threshold=1),
                    action=PolicyAction(action_type=ActionType.NOTIFY_USER, description="Reduce LLM dependency and optimize local execution"),
                    priority=2
                )
                self.orc.policy.add_rule(rule)

    async def _execute(self, task):
        """
        Executes a single task with retries, ethical checks, and optional chunked refactor logic.
        """
        logger.debug(f"[START] Executing task: {task.name} (agent={task.agent}, id={task.id})")
        task.mark_running()
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
            logger.debug(f"[END] Task: {task.name} (agent={task.agent}, id={task.id}) | Blocked by EthicalGuard")
            return

        agent = await self._get_agent_for_task(task)
        if not agent:
            task.mark_failed("No agent available")
            logger.error(f"[FAILED] Task: {task.name} (agent={task.agent}, id={task.id}) | No agent available")
            logger.debug(f"[END] Task: {task.name} (agent={task.agent}, id={task.id}) | No agent available")
            return

        heartbeat_task = asyncio.create_task(self._heartbeat())

        try:
            result = await self._execute_task_logic(task, agent)
        except asyncio.TimeoutError:
            heartbeat_task.cancel()
            retries = self._retry_counts.get(task.id, 0)
            if retries < self.max_retries:
                self._retry_counts[task.id] = retries + 1
                logger.warning(f"Task '{task.name}' timed out — retry {retries+1}/{self.max_retries}")
                task.status = TaskStatus.PENDING  # reset for retry
                logger.debug(f"[RETRY] Task: {task.name} (agent={task.agent}, id={task.id}) | Timeout, retry {retries+1}")
                return
            else:
                debugger = self.orc.get_agent("debugger")
                if debugger:
                    await debugger.execute({"name": f"Debug: {task.name}", "data": {"error": "Timeout after retries", "task": task.to_dict()}})
                task.mark_failed("Timeout after retries")
                logger.error(f"[FAILED] Task: {task.name} (agent={task.agent}, id={task.id}) | Timed out after {self.max_retries} retries")
                logger.debug(f"[END] Task: {task.name} (agent={task.agent}, id={task.id}) | Timed out after retries")
                return
        except Exception as e:
            heartbeat_task.cancel()
            retries = self._retry_counts.get(task.id, 0)
            if retries < self.max_retries:
                self._retry_counts[task.id] = retries + 1
                logger.warning(f"Task '{task.name}' error: {e} — retry {retries+1}/{self.max_retries}")
                task.status = TaskStatus.PENDING  # reset for retry
                logger.debug(f"[RETRY] Task: {task.name} (agent={task.agent}, id={task.id}) | Exception, retry {retries+1}")
                return
            else:
                print(f"⚠️ [AMRIT] ਗਲਤੀ ਆਈ: {e}\nਕਿਰਪਾ ਕਰਕੇ ਕੋਡ ਜਾਂ ਇੰਸਟਾਲੇਸ਼ਨ ਜਾਂਚੋ। (Swarm will continue)")
                debugger = self.orc.get_agent("debugger")
                if debugger:
                    await debugger.execute({"name": f"Debug: {task.name}", "data": {"error": str(e), "task": task.to_dict()}})
                task.mark_failed(str(e))
                logger.error(f"[FAILED] Task: {task.name} (agent={task.agent}, id={task.id}) | Failed after {self.max_retries} retries: {e}")
                await self.orc.event_bus.publish("agent.error",
                    {"agent": task.agent, "task": task.name, "error": str(e)})
                logger.debug(f"[END] Task: {task.name} (agent={task.agent}, id={task.id}) | Failed after retries")
                return
        finally:
            heartbeat_task.cancel()

        task.mark_done(result)
        await self.orc.event_bus.publish("task.complete",
            {"id": task.id, "name": task.name, "result": result}, source=task.agent)
        logger.debug(f"[END] Task: {task.name} (agent={task.agent}, id={task.id}) | Completed successfully")

    async def _get_agent_for_task(self, task):
        if hasattr(self.orc, 'get_or_create_agent'):
            agent = await self.orc.get_or_create_agent(task.agent, task.to_dict().get('data'))
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
        # Intercept code-modifying tasks and route through UpgradeAgent patch loop
        is_code_mod = False
        patch_result = None
        is_refactor = False
        if hasattr(task, 'data') and isinstance(task.data, dict):
            action = task.data.get('action', '').lower()
            if action in {'patch', 'modify_code', 'apply_patch', 'code_patch'}:
                is_code_mod = True
            if action == 'refactor':
                is_refactor = True
        if is_code_mod and task.data.get('file') and task.data.get('new_code'):
            upgrade_agent = self.orc.get_agent('upgrade')
            tester_agent = self.orc.get_agent('tester')
            patch_result = await upgrade_agent.apply_patch_and_test(
                task.data['file'], task.data['new_code'], tester_agent, task_name=task.name)
            return patch_result
        elif is_refactor:
            chunked_result = await self._chunked_refactor(task, chunk_size=40)
            if chunked_result:
                return chunked_result
            else:
                return await asyncio.wait_for(agent.execute(task.to_dict()), timeout=task.timeout)
        else:
            return await asyncio.wait_for(agent.execute(task.to_dict()), timeout=task.timeout)

    async def _chunked_refactor(self, task, chunk_size: int = 40):
        """
        If the refactor target is a large function, split into smaller chunks and refactor each.
        chunk_size: max lines per chunk (default 40)
        """
        import re
        code = task.data.get('code') or task.data.get('new_code')
        if not code:
            return None
        line_count = code.count('\n')
        if line_count < chunk_size * 1.5:
            return None  # Not a large function, skip chunking
        logger.info(f"[Chunked Refactor] Large function detected in {task.data.get('file','?')} ({line_count} lines). Splitting for chunked refactor (chunk_size={chunk_size}).")
        split_regex = r'^(def |class )'
        parts = re.split(split_regex, code, flags=re.MULTILINE)
        chunks = []
        if len(parts) >= 3:
            for i in range(1, len(parts), 2):
                chunks.append(parts[i] + parts[i+1])
        else:
            lines = code.splitlines()
            for i in range(0, len(lines), chunk_size):
                chunk = '\n'.join(lines[i:i+chunk_size])
                chunks.append(chunk)
        merged_chunks = []
        buf = ""
        for chunk in chunks:
            if buf and (buf.count('\n') + chunk.count('\n')) < chunk_size:
                buf += '\n' + chunk
            else:
                if buf:
                    merged_chunks.append(buf)
                buf = chunk
        if buf:
            merged_chunks.append(buf)
        refactored_chunks = []
        for idx, chunk in enumerate(merged_chunks):
            subtask = task.to_dict().copy()
            subtask['data'] = dict(task.data)
            subtask['data']['code'] = chunk
            subtask['data']['new_code'] = chunk
            logger.info(f"[Chunked Refactor] Refactoring chunk {idx+1}/{len(merged_chunks)} ({len(chunk.splitlines())} lines)")
            try:
                agent = self.orc.get_agent(task.agent)
                refactored = await asyncio.wait_for(agent.execute(subtask), timeout=task.timeout)
                refactored_code = refactored.get('code') if isinstance(refactored, dict) else refactored
                if not refactored_code or 'invalid syntax' in str(refactored_code):
                    logger.warning(f"[Chunked Refactor] Chunk {idx+1} failed syntax check. Keeping original.")
                    refactored_code = chunk
                refactored_chunks.append(refactored_code)
            except Exception as e:
                logger.error(f"[Chunked Refactor] Exception in chunk {idx+1}: {e}. Keeping original.")
                refactored_chunks.append(chunk)
        logger.info(f"[Chunked Refactor] All chunks processed. Reassembling.")
        return {'code': '\n'.join(refactored_chunks)}

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