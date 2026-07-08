"""
Workflow Engine — YAML-defined multi-step workflow execution.
Supports conditional steps, loops, parallel execution, and variables.
"""
import yaml
import asyncio
from pathlib import Path
from logger import setup_logger

logger = setup_logger("WorkflowEngine")


class WorkflowStep:
    def __init__(self, raw: dict):
        self.name      = raw.get("name", "step")
        self.agent     = raw.get("agent", "tool")
        self.action    = raw.get("action", "")
        self.data      = raw.get("data", {})
        self.condition = raw.get("if", None)
        self.loop      = raw.get("loop", None)
        self.parallel  = raw.get("parallel", False)
        self.on_fail   = raw.get("on_fail", "stop")  # stop | continue | retry
        self.timeout   = raw.get("timeout", 60)


class WorkflowEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._variables: dict = {}

    async def run_file(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {"status": "error", "error": f"Workflow file not found: {path}"}
        with open(p) as f:
            spec = yaml.safe_load(f)
        return await self.run(spec)

    async def run(self, spec: dict) -> dict:
        name   = spec.get("name", "workflow")
        steps  = spec.get("steps", [])
        self._variables = spec.get("variables", {})

        logger.info(f"Workflow '{name}' starting ({len(steps)} steps)")
        results = []

        for raw_step in steps:
            step = WorkflowStep(raw_step)

            # Evaluate condition
            if step.condition and not self._eval_condition(step.condition):
                logger.info(f"Step '{step.name}' skipped (condition false)")
                results.append({"step": step.name, "status": "skipped"})
                continue

            # Handle loop
            if step.loop:
                loop_results = await self._run_loop(step)
                results.extend(loop_results)
                continue

            result = await self._run_step(step)
            results.append(result)

            if result.get("status") == "error" and step.on_fail == "stop":
                logger.error(f"Workflow halted at step '{step.name}'")
                break

            # Store output as variable
            out_key = raw_step.get("output_var")
            if out_key:
                self._variables[out_key] = result

        logger.info(f"Workflow '{name}' complete: {len(results)} steps")
        return {"status": "complete", "name": name, "steps": results,
                "variables": self._variables}

    async def _run_step(self, step: WorkflowStep) -> dict:
        agent = self.orchestrator.get_agent(step.agent)
        if not agent:
            return {"step": step.name, "status": "error", "error": f"Agent '{step.agent}' not found"}

        task = {"name": step.name, "agent": step.agent,
                "data": {**step.data, "action": step.action}}
        try:
            result = await asyncio.wait_for(agent.execute(task), timeout=step.timeout)
            return {"step": step.name, "status": "ok", "result": result}
        except asyncio.TimeoutError:
            return {"step": step.name, "status": "error", "error": "Timeout"}
        except Exception as e:
            return {"step": step.name, "status": "error", "error": str(e)}

    async def _run_loop(self, step: WorkflowStep) -> list:
        items = self._variables.get(step.loop, [])
        results = []
        if step.parallel:
            tasks = [self._run_step_with_item(step, item) for item in items]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            for item in items:
                r = await self._run_step_with_item(step, item)
                results.append(r)
        return results

    async def _run_step_with_item(self, step: WorkflowStep, item) -> dict:
        step.data["item"] = item
        return await self._run_step(step)

    def _eval_condition(self, condition: str) -> bool:
        try:
            return bool(eval(condition, {"__builtins__": {}}, self._variables))
        except Exception:
            return True
