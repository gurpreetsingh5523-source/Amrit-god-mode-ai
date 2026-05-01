
import time
from pathlib import Path
from base_agent import BaseAgent
from ethical_guard import EthicalGuard
from patch_safety import validate_patch, backup_file, auto_recover, record_patch_failure


class UpgradeAgent(BaseAgent):
    async def apply_patch_and_test(self, file_path: str, new_code: str, tester_agent=None, task_name="auto_patch"):
        from experience_log import ExperienceLog
        old_code = Path(file_path).read_text(errors="ignore")
        backup_file(file_path)
        Path(file_path).write_text(new_code)
        is_safe, reason = validate_patch(file_path, old_code, new_code)
        if not is_safe:
            self.logger.warning(f"❌ BLOCKED FIX: {reason}")
            auto_recover(file_path, logger=self.logger)
            record_patch_failure(self.name, file_path, reason, task=task_name)
            return {"status": "error", "reason": reason, "stage": "syntax"}
        # Run tests if syntax is OK
        if tester_agent:
            test_result = await tester_agent.execute({"data": {"action": "run", "target": file_path}})
            if test_result.get("status") != "ok" or test_result.get("failed", 0) > 0:
                fail_reason = test_result.get("output", "Test(s) failed")
                self.logger.warning(f"❌ TEST FAILED: {fail_reason}")
                auto_recover(file_path, logger=self.logger)
                record_patch_failure(self.name, file_path, fail_reason, task=task_name)
                return {"status": "error", "reason": fail_reason, "stage": "test"}
        return {"status": "ok"}

    def __init__(self, eb, state):
        super().__init__("UpgradeAgent", eb, state)
        self.guard = EthicalGuard()

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "analyze")
        await self.report(f"Upgrade [{action}]")
        if action == "analyze":
            return await self._analyze()
        elif action == "suggest":
            return await self._suggest(d.get("file",""))
        elif action == "benchmark":
            return await self._benchmark()
        elif action == "install":
            return await self._install(d.get("package",""))
        else:
            return await self._analyze()

    async def _analyze(self) -> dict:
        py_files = list(Path(".").rglob("*.py"))[:30]
        todos = []
        for f in py_files:
            try:
                code = f.read_text(errors="ignore")
                for i, ln in enumerate(code.splitlines(), 1):
                    if "TODO" in ln or "NotImplementedError" in ln:
                        todos.append({"file": str(f), "line": i, "text": ln.strip()})
            except Exception as e: 
                print(e)
        todos_str = f"{todos[:5] if todos else 'None'}"
        prompt = f"""
TODOs: {todos_str}
Analyze this AI system ({len(py_files)} Python files, {len(todos)}) and fix all issues. Keep all existing functionality. Return ONLY the fixed code.
"""
        analysis = await self.ask_llm(prompt=prompt)
        await self.set_state("last_analysis", analysis[:500])
        # DEMO: Simulate a patch for the first file with a TODO (if any)
        patch_result = None
        if todos:
            file_path = todos[0]["file"]
            old_code = Path(file_path).read_text(errors="ignore")
            # For demo, just add a comment to the first TODO line
            lines = old_code.splitlines()
            todo_line = todos[0]["line"] - 1
            if 0 <= todo_line < len(lines):
                lines[todo_line] += "  # PATCHED"
                new_code = "\n".join(lines)
                # Find TesterAgent
                tester_agent = None
                if hasattr(self, "event_bus") and hasattr(self.event_bus, "orchestrator"):
                    tester_agent = self.event_bus.orchestrator.get_agent("tester")
                patch_result = await self.apply_patch_and_test(file_path, new_code, tester_agent)
        return self.ok(files=len(py_files), todos=len(todos), analysis=analysis, patch_result=patch_result)

    async def _suggest(self, filepath: str) -> dict:
        p = Path(filepath)
        if not p.exists():
            return self.err(f"Not found: {filepath}")
        code = p.read_text(errors="ignore")
        prompt = f"Suggest improvements for:\n{code[:3000]}"
        suggestions = await self.ask_llm(prompt=prompt)
        return self.ok(file=filepath, suggestions=suggestions)

    async def _benchmark(self) -> dict:
        times = {}
        mods = ["core.orchestrator", "core.task_graph", "agents.base_agent"]
        for mod in mods:
            t0 = time.perf_counter()
            try:
                __import__(mod)
            except ImportError:
                pass
            times[mod] = round(time.perf_counter() - t0, 4)
        return self.ok(import_times=times)

    async def _install(self, package) -> dict:
        safe, reason = await self.guard.check(f"pip install {package}")
        if not safe:
            return self.err(f"Action FAILED: Blocked by EthicalGuard because {reason}. Find a safer alternative.")
        
        import subprocess
        try:
            result = subprocess.run(["pip", "install", package], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Installation failed with error: {result.stderr}")
        except Exception as e:
            print(f"Exception during installation: {e}")
        
        return self.ok(package=package)