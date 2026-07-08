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

    @staticmethod
    def _fix_imports(tests: str, mod_name: str, is_fastapi: bool = False) -> str:
        """LLMs stubbornly mis-import the module (`from main import app`). Rather than
        fight it, STRIP the model's module-import / client-setup lines and PREPEND a
        known-correct header. This guarantees the import resolves."""
        wrongs = ("main", "app", "api", "server", "application", mod_name)
        kept = []
        for ln in tests.splitlines():
            s = ln.strip()
            # drop module imports, the TestClient import, and client=TestClient(...) —
            # we re-add these in a controlled order in the header.
            if re.match(rf"^(from|import)\s+({'|'.join(wrongs)})\b", s):
                continue
            if re.match(r"^from fastapi\.testclient import TestClient", s):
                continue
            if re.match(r"^client\s*=\s*TestClient\(", s):
                continue
            kept.append(ln)
        body = "\n".join(kept).strip()

        header = [f"import {mod_name}"]
        if is_fastapi:
            header.append("from fastapi.testclient import TestClient")
            header.append(f"client = TestClient({mod_name}.app)")
        # normalise lingering references to the wrong module name, including
        # string targets inside @patch("main.get_db") / mock.patch('app.x').
        for w in ("main", "app", "api", "server", "application"):
            if w != mod_name:
                body = re.sub(rf"\b{w}\.app\b", f"{mod_name}.app", body)
                body = re.sub(rf"(['\"]){w}\.", rf"\g<1>{mod_name}.", body)  # patch("main.x")
        return "\n".join(header) + "\n\n" + body

    @staticmethod
    def _extract_code(text: str) -> str:
        """Pull runnable code out of an LLM reply that may wrap it in a
        ```python fenced block and/or surround it with prose."""
        text = (text or "").strip()
        # Prefer the largest fenced code block if present
        blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
        if blocks:
            return max(blocks, key=len).strip()
        # No fences: drop any leading prose lines until real code starts
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if re.match(r"^\s*(import |from |def |class |@|#!|\"\"\")", ln):
                return "\n".join(lines[i:]).strip()
        return text

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "run")
        await self.report(f"Tester [{action}]")
        if action == "generate":
            return await self._gen_tests(d)
        if action == "run_code":
            return await self._run_snippet(d.get("code",""))
        if action == "validate":
            return await self._validate(d)
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
        code = d.get("code", "")
        out_base = Path(d.get("output_dir") or "workspace")
        if not str(out_base).startswith("workspace"):
            out_base = Path("workspace") / out_base
        out_base.mkdir(parents=True, exist_ok=True)

        # If no code passed, find the target module to test (e.g. api.py the
        # swarm just generated) so we test REAL code, not an empty string.
        target = d.get("filename") or d.get("target") or ""
        spec = d.get("spec", "")
        if not code:
            cand = None
            if target and (out_base / target).exists():
                cand = out_base / target
            else:  # find the most relevant .py in the output dir
                import re as _re
                hint = _re.search(r'(\w+\.py)', spec)
                if hint and (out_base / hint.group(1)).exists():
                    cand = out_base / hint.group(1)
                else:
                    pys = [p for p in out_base.glob("*.py") if not p.name.startswith("test_")]
                    cand = pys[0] if pys else None
            if cand:
                code = cand.read_text()
                target = cand.name

        if not code:
            return self.err("No code/target found to test")

        mod_name = target[:-3] if target.endswith(".py") else "module"
        p = out_base / f"test_{mod_name}.py"
        max_rounds = int(d.get("max_rounds", 3))
        is_fastapi = ("FastAPI" in code or "@app." in code)

        if is_fastapi:
            skeleton = (
                f"import {mod_name}\n"
                f"from fastapi.testclient import TestClient\n"
                f"client = TestClient({mod_name}.app)\n\n"
                f"def test_<name>():\n"
                f"    resp = client.get('/<path>')   # or client.post(...)\n"
                f"    assert resp.status_code == 200\n"
            )
        else:
            skeleton = (
                f"import {mod_name}\n\n"
                f"def test_<name>():\n"
                f"    assert {mod_name}.<function>(<args>) == <expected>\n"
            )

        base_prompt = (
            f"You are writing a pytest TEST FILE (not module code) for the module "
            f"'{mod_name}'. Output ONLY the test file.\n\n"
            f"RULES:\n"
            f"- Import the module EXACTLY as `import {mod_name}` (file is {mod_name}.py; "
            f"never import 'main' or guess names).\n"
            f"- Every test function name MUST start with `test_`.\n"
            f"- Test ONLY the real public interface shown below. Do NOT call functions/"
            f"attributes that don't appear in the module.\n"
            + ("- For FastAPI, use TestClient and call the HTTP endpoints.\n" if is_fastapi else "")
            + f"- Do NOT redefine the module's code. Do NOT write any prose.\n\n"
            f"FOLLOW THIS SKELETON:\n```python\n{skeleton}```\n\n"
            f"THE MODULE {mod_name}.py (test against this real interface):\n"
            f"```python\n{code[:6000]}\n```\n\n"
            f"Now output the complete test file (start with the imports):"
        )
        tests = self._fix_imports(self._extract_code(await self.ask_llm(base_prompt, max_tokens=3000)), mod_name, is_fastapi)

        # ── SELF-VERIFY LOOP: run the tests; if they fail, feed the error
        # back and regenerate, until they PASS (or rounds exhausted). ──
        last_err = ""
        for rnd in range(1, max_rounds + 1):
            p.write_text(tests)
            # Start each verification from a CLEAN slate — leftover *.db from a
            # prior round pollutes state and makes passing tests look failed.
            for dbf in out_base.glob("*.db"):
                try: dbf.unlink()
                except Exception: pass
            r = subprocess.run(
                [sys.executable, "-m", "pytest", p.name, "-q", "--tb=short", "-p", "no:cacheprovider"],
                capture_output=True, text=True, timeout=90, cwd=str(out_base))
            out = (r.stdout + r.stderr)
            if r.returncode == 0 and "passed" in out:
                n = tests.count("def test_")
                await self.report(f"✅ self-verified tests: {p} ({n} tests pass, round {rnd})")
                return self.ok(test_code=tests, file=str(p), verified=True,
                               rounds=rnd, tests=n)

            last_err = out[-1500:]
            await self.report(f"  🔧 test round {rnd} failed — self-healing", level="info")
            if rnd < max_rounds:
                fix_prompt = (
                    f"This pytest TEST FILE fails. Rewrite the TEST FILE so it PASSES.\n"
                    f"Output ONLY the corrected test file code — NO prose, NO explanation, "
                    f"and do NOT output the module's code. Start with `import {mod_name}`.\n"
                    f"Test only the real public interface (HTTP endpoints for FastAPI). "
                    f"Do NOT reference functions/attributes that don't exist in the module.\n\n"
                    f"PYTEST ERROR:\n{last_err}\n\n"
                    f"THE MODULE ({mod_name}.py) — test against THIS real interface:\n"
                    f"```python\n{code[:3500]}\n```\n\n"
                    f"CURRENT FAILING TEST FILE:\n```python\n{tests[:3000]}\n```"
                )
                tests = self._fix_imports(self._extract_code(await self.ask_llm(fix_prompt, max_tokens=3000)), mod_name, is_fastapi)

        # Never passed — keep file but flag unverified (honest)
        p.write_text(tests)
        await self.report(f"⚠️ tests for {mod_name} not passing after {max_rounds} rounds — saved unverified",
                          level="warning")
        return self.ok(test_code=tests, file=str(p), verified=False,
                       rounds=max_rounds, last_error=last_err[:400])

    async def _run_snippet(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py",delete=False,mode="w") as f:
            f.write(code)
            tmp = f.name
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
