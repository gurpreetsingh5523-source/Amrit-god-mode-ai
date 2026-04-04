"""Tester Agent — pytest execution, test generation, code validation."""
import subprocess
import os
import re
import tempfile
import sys
from pathlib import Path
from base_agent import BaseAgent

class TesterAgent(BaseAgent):
    def __init__(self, eb, state): super().__init__("TesterAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "run")
        await self.report(f"Tester [{action}]")
        if action == "generate": return await self._gen_tests(d)
        if action == "run_code": return await self._run_snippet(d.get("code",""))
        if action == "validate": return await self._validate(d)
        return await self._run_tests(d.get("target","tests/"))

    async def _run_tests(self, target: str) -> dict:
        # Use the current Python executable (sys.executable) so subprocesses
        # run with the same interpreter / venv that started this process.
        r = subprocess.run([
            sys.executable, "-m", "pytest", target, "-v", "--tb=short", "-q"
        ], capture_output=True, text=True, timeout=60)
        out = r.stdout + r.stderr
        return self.ok(
            passed=len(re.findall(r"\bPASSED\b", out)),
            failed=len(re.findall(r"\bFAILED\b", out)),
            output=out[:2000],
            returncode=r.returncode,
        )

    async def _gen_tests(self, d: dict) -> dict:
        code = d.get("code","")
        tests = await self.ask_llm(
            f"Write comprehensive pytest tests for:\n{code}\n"
            "Cover happy path, edge cases, errors. Return only test code.")
        tests = re.sub(r"```python\n?|```","",tests).strip()
        p = Path("tests/test_generated.py")
        p.parent.mkdir(exist_ok=True)
        p.write_text(tests)
        return self.ok(test_code=tests, file=str(p))

    async def _run_snippet(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py",delete=False,mode="w") as f:
            f.write(code); tmp = f.name
        try:
            r = subprocess.run([sys.executable,tmp],capture_output=True,text=True,timeout=15)
            return self.ok(stdout=r.stdout,stderr=r.stderr,returncode=r.returncode)
        except subprocess.TimeoutExpired:
            return self.err("Timeout")
        finally:
            os.unlink(tmp)

    async def _validate(self, d: dict) -> dict:
        r = await self._run_snippet(d.get("code",""))
        actual   = r.get("stdout","").strip()
        expected = d.get("expected","").strip()
        return self.ok(match=actual==expected, actual=actual, expected=expected)
