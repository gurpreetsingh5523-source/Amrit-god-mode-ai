import time
from pathlib import Path
from base_agent import BaseAgent
from ethical_guard import EthicalGuard

class UpgradeAgent(BaseAgent):
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
        
        return self.ok(files=len(py_files), todos=len(todos), analysis=analysis)

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
            try: __import__(mod)
            except ImportError as e: pass
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