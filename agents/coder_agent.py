from toolbox import ToolBox
from toolbox_persistence import ToolBoxPersistence
import asyncio
"""Coder Agent — Multi-language code generation, fixing, refactoring, testing."""
import ast
import re
import subprocess
import tempfile
from pathlib import Path
from base_agent import BaseAgent


# Language-specific first-token patterns for _strip() detection
_LANG_STARTS = {
    "python":     ("def ", "async def ", "class ", "import ", "from ", "@", "#"),
    "javascript": ("function ", "const ", "let ", "var ", "class ", "import ", "export ", "//"),
    "typescript": ("function ", "const ", "let ", "var ", "class ", "import ", "export ", "interface ", "type ", "//"),
    "rust":       ("fn ", "use ", "mod ", "pub ", "struct ", "enum ", "impl ", "//", "#["),
    "go":         ("package ", "import ", "func ", "type ", "var ", "const ", "//"),
    "java":       ("public ", "private ", "protected ", "class ", "import ", "package ", "//"),
    "bash":       ("#!/", "set ", "export ", "function ", "echo ", "#"),
    "html":       ("<!DOCTYPE", "<html", "<head", "<body", "<!--"),
    "css":        ("/*", ".", "#", "@", ":root"),
}
_DEFAULT_STARTS = ("def ", "class ", "import ", "from ", "#", "//", "/*", "fn ", "func ")



class CoderAgent(BaseAgent):
    """
    CoderAgent handles multi-language code generation, fixing, refactoring, testing, and code review.
    Integrates with ToolBox for dynamic tool management and uses LLMs for code tasks.
    """
    # Common libraries worth grounding with real open-source patterns.
    _KNOWN_LIBS = [
        "3d-force-graph", "force-graph", "three.js", "fastapi", "flask", "django",
        "react", "vue", "chart.js", "d3", "pandas", "numpy", "playwright",
        "express", "tailwind", "sqlalchemy", "pydantic", "langchain",
    ]

    async def _recall_or_learn_patterns(self, text: str) -> str:
        """Detect a library in the task and return REAL API patterns for it —
        recalled from learning_data.json, or learned from GitHub on a miss.
        Bounded: at most one library per call, cached after first learn."""
        try:
            import asyncio
            from github_learner import GitHubLearner
        except Exception:
            return ""
        low = (text or "").lower()
        lib = next((l for l in self._KNOWN_LIBS if l in low), None)
        if not lib:
            return ""
        try:
            gl = GitHubLearner()
            hit = gl.recall_patterns(lib)
            if not (hit and hit.get("patterns")):
                # cache-miss → learn once (docs-first, tiny), runs in a thread
                res = await asyncio.to_thread(gl.learn, lib, 1, 2)
                pats = getattr(res, "patterns", []) or []
            else:
                pats = hit["patterns"]
            if pats:
                await self.report(f"📚 grounded with {len(pats)} learned '{lib}' API patterns")
                return "\n".join(f"- {p}" for p in pats[:12])
        except Exception as e:
            await self.report(f"pattern recall skipped: {e}")
        return ""

    @staticmethod
    def _looks_complete(code: str, lang: str) -> bool:
        """True if `code` looks like a COMPLETE file (not truncated mid-output).
        Used so the shrinkage guard allows legit smaller rewrites but still
        blocks genuinely cut-off responses."""
        c = (code or "").strip()
        if len(c) < 400:
            return False
        if lang == "python":
            try:
                ast.parse(c)
                return True
            except SyntaxError:
                return False
        low = c.lower()
        if "<html" in low or "<!doctype" in low or "<body" in low:
            # HTML must close its document, not end mid-tag.
            return "</html>" in low or "</body>" in low
        # generic: shouldn't end mid-string/બracket
        return c[-1] in "}>);\n]'\"`" or low.endswith(("</script>", "</style>"))

    @staticmethod
    def resolve_output_path(output_dir, fn):
        """Resolve (out_base, basename). output_dir is authoritative; a filename
        that carries a directory is reduced to its basename so we never get the
        "workspace/x/workspace/x/file" doubling bug. Pure + testable."""
        out_base = Path(output_dir or "workspace")
        if not str(out_base).startswith("workspace"):
            out_base = Path("workspace") / out_base
        if fn:
            fn = Path(fn).name
        return out_base, fn

    def __init__(self, eb: object, state: dict) -> None:
        """
        Initialize the CoderAgent with event bus and state.
        Creates workspace directory and loads dynamic tools.
        """
        super().__init__("CoderAgent", eb, state)
        Path("workspace").mkdir(exist_ok=True)
        self.toolbox = ToolBox()
        self.toolbox_persistence = ToolBoxPersistence()
        for name, desc in self.toolbox_persistence.load_tools().items():
            self.toolbox.create_tool(name, desc)

    def save_dynamic_tools(self) -> None:
        """Persist dynamic tools to storage."""
        self.toolbox_persistence.save_tools(self.toolbox.tools)

    # ------------------------------------------------------------------ #
    #  Router                                                              #
    # ------------------------------------------------------------------ #

    async def execute(self, task: dict) -> dict:
        """
        Main entry point for agent actions. Dispatches to the correct handler based on action.
        Validates input and logs the action.
        """
        d = task.get("data", {})
        action = d.get("action", "generate")
        await self.report(f"Coder [{action}]")
        dispatch = {
            "generate": self._gen,
            "fix":      self._fix,
            "refactor": self._refactor,
            "explain":  self._explain,
            "review":   self._review,
            "test":     self._test,
        }
        handler = dispatch.get(action, self._gen)
        if not callable(handler):
            await self.report(f"Unknown action: {action}, defaulting to generate.")
            handler = self._gen
        return await handler(d)

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    async def _gen(self, d: dict) -> dict:
        """
        Generate code for a given specification or goal. If a filename is provided and exists,
        extend/improve the code; otherwise, create new code. Validates Python syntax before saving.
        """
        lang: str = d.get("language", "python")
        spec: str = d.get("spec") or d.get("goal") or d.get("name", "")
        goal: str = d.get("goal", spec)
        fn: str = d.get("filename", "")

        # Try to extract target filename from spec/goal (e.g. "sandman_face.py")
        _known_ext = r'(?:py|js|ts|rs|go|java|sh|html|css|c|cpp|h|rb|php|swift|kt)'
        if not fn:
            m = re.search(rf'(\w+\.{_known_ext})\b', spec)
            if m:
                fn = m.group(1)

        # Output base dir — honor a requested subdir (e.g. workspace/expense_app)
        # instead of always dumping into workspace/ root.
        out_base, fn = self.resolve_output_path(d.get("output_dir"), fn)
        out_base.mkdir(parents=True, exist_ok=True)

        # If target file already exists, read it and extend/improve
        existing_code: str = ""
        if fn:
            existing_path = out_base / fn
            if existing_path.exists():
                existing_code = existing_path.read_text()

        if existing_code:
            prompt = (
                f"You are building: {goal}\n"
                f"Current task: {spec}\n\n"
                f"Here is the EXISTING code in {fn}:\n```{lang}\n{existing_code}\n```\n\n"
                f"Extend and improve this code to fulfill the task. "
                f"Return the COMPLETE updated file with ALL existing functionality preserved "
                f"plus the new features. Return ONLY code, no explanations."
            )
        else:
            run_cmd = f"python3 {fn or 'app.py'}" if lang == "python" else f"node {fn or 'app.js'}"
            prompt = (
                f"You are building: {goal}\n"
                f"Current task: {spec}\n\n"
                f"Write a COMPLETE, working {lang} file that implements this.\n"
                f"Requirements:\n"
                f"- The code must be runnable as-is with `{run_cmd}`\n"
                f"- Include all imports at the top\n"
                f"- Handle errors gracefully\n"
                f"- Return ONLY code inside a single ```{lang} code block, no explanations."
            )

        # Inject REAL API patterns learned from open source so the model uses
        # verified method names instead of hallucinating (e.g. the bogus
        # linkDirectionalParticleTailLength). Recall first; learn on a miss.
        learned = await self._recall_or_learn_patterns(f"{goal} {spec} {fn}")
        if learned:
            prompt += ("\n\nVERIFIED API patterns learned from real open-source repos "
                       "(use ONLY these real methods, do not invent others):\n" + learned)

        # Phase 2 — cross-session CONTINUITY: recall Amrit's own past task outcomes
        # so it repeats what worked and avoids what failed.
        try:
            from task_memory import TaskMemory
            self._task_mem = getattr(self, "_task_mem", None) or TaskMemory()
            past = self._task_mem.recall_text(f"{goal} {spec}")
            if past:
                prompt += ("\n\nYOUR OWN PAST EXPERIENCE on similar tasks "
                           "(repeat what worked, avoid what failed):\n" + past)
                await self.report(f"🧠 recalled {len(past.splitlines())} past experience(s)")
        except Exception:
            self._task_mem = None

        # Large budget so big files (full HTML dashboards, multi-class modules)
        # are not truncated mid-file — the old 2000 default cut large outputs.
        code: str = await self.ask_llm(prompt, max_tokens=8000)
        code = self._strip(code, lang)

        # Validate Python syntax before saving
        if lang == "python":
            ok, err = self._py_syntax_check(code)
            if not ok:
                await self.report(f"Syntax error in generated code — asking LLM to fix: {err}")
                code = await self._llm_fix_code(code, err, lang)

        # Determine output file
        if not fn and spec:
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', spec.lower())[:40].strip('_')
            ext  = self._default_ext(lang)
            fn   = f"{safe}{ext}"

        # SMART SHRINKAGE GUARD: a much-smaller response is only DATA LOSS if it
        # also looks TRUNCATED/incomplete. A complete, valid, substantial rewrite
        # (e.g. a cleaner HTML that drops bloat from heal rounds) is legitimate —
        # do not block it just for being smaller.
        if existing_code and code and len(code) < len(existing_code) * 0.6:
            if not self._looks_complete(code, lang):
                await self.report(
                    f"⚠️ rejected extend of {fn}: new code ({len(code)}b) looks "
                    f"TRUNCATED vs existing ({len(existing_code)}b) — keeping original",
                    level="warning")
                return self.ok(code=existing_code, language=lang, filename=fn,
                               lines=len(existing_code.splitlines()), kept_original=True)
            await self.report(
                f"✓ accepting smaller rewrite of {fn} ({len(code)}b<{len(existing_code)}b): "
                f"complete & valid (likely intentional cleanup)")

        if fn:
            p = out_base / fn
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code)
            await self.report(f"Saved: {p} ({len(code.splitlines())} lines)")

            # AUTO web self-verify+heal for HTML output (browser console errors).
            if fn.lower().endswith((".html", ".htm")):
                try:
                    import asyncio
                    from web_verify import verify_and_heal
                    vr = await asyncio.to_thread(
                        verify_and_heal, str(p), 2, spec
                    )
                    if vr.get("ok"):
                        await self.report(f"✅ web-verify: {fn} loads clean "
                                          f"(canvas={vr.get('canvas',0)}, fixed={vr.get('errors_fixed',0)})")
                        code = p.read_text()  # may have been healed
                    else:
                        await self.report(f"⚠️ web-verify: {fn} still has issues: "
                                          f"{vr.get('final_errors', [])[:2]}", level="warning")
                except Exception as e:
                    await self.report(f"web-verify skipped: {e}", level="debug")

        # Phase 2 — RECORD this task's outcome so future similar tasks recall it.
        try:
            if getattr(self, "_task_mem", None):
                note = f"{lang}" + (f" file {fn}" if fn else "") + " via coder"
                self._task_mem.record(spec or goal, success=bool(code), note=note)
        except Exception:
            pass

        return self.ok(code=code, language=lang, filename=fn, lines=len(code.splitlines()))

    async def _fix(self, d: dict) -> dict:
        """
        Fix code using LLM based on an error message. Validates Python syntax after fix.
        """
        code  = d.get("code", "")
        err   = d.get("error", "")
        lang  = d.get("language", "python")
        fn    = d.get("filename", "")

        fixed = await self._llm_fix_code(code, err, lang)

        # Validate fixed Python before accepting
        if lang == "python":
            ok, syntax_err = self._py_syntax_check(fixed)
            if not ok:
                await self.report(f"LLM fix still has syntax error: {syntax_err} — returning original with error note")
                return self.ok(
                    code=code,
                    fixed=False,
                    original_error=err,
                    fix_error=syntax_err,
                )

        # Overwrite workspace file if filename provided
        if fn:
            p = Path("workspace") / fn
            if p.exists():
                p.write_text(fixed)
                await self.report(f"Fixed and saved: workspace/{fn}")

        return self.ok(code=fixed, fixed=True, fixed_error=err)

    async def _refactor(self, d: dict) -> dict:
        """
        Refactor code for readability or other goals. Uses LLM and validates Python syntax.
        """
        goal         = d.get("goal", "improve readability")
        instructions = d.get("error", "")       # self_evolution passes instructions via 'error'
        category     = d.get("category", "refactor")
        lang         = d.get("language", "python")
        fn           = d.get("filename", "")
        original     = d.get("code", "")

        from llm_router import LLMRouter
        router = LLMRouter()
        model  = router._pick_model_for_category(category)

        prompt = (
            f"{instructions}\n\nCode to refactor:\n```{lang}\n{original}\n```\n"
            "Return ONLY valid code inside a single code block. "
            "No explanations, no markdown outside the code block."
        ) if instructions else (
            f"Refactor to {goal}:\n```{lang}\n{original}\n```\n"
            f"Return only valid {lang} code in a ```{lang} block."
        )

        # Bypass ask_llm summarisation — it can corrupt code
        code = await router.complete(
            prompt,
            system=(
                f"You are a {lang} refactoring expert. "
                "Output ONLY valid code. Never include explanations outside code blocks."
            ),
            model=model,
            max_tokens=4000,
        )
        code = self._strip(code, lang)

        # Python syntax validation
        if lang == "python":
            ok, err = self._py_syntax_check(code)
            if not ok:
                await self.report(f"Refactor produced invalid syntax ({err}) — keeping original")
                return self.ok(code=original, refactored=False, error=err)

        # Save if filename provided
        if fn:
            p = Path("workspace") / fn
            if p.exists():
                p.write_text(code)
                await self.report(f"Refactored and saved: workspace/{fn}")

        return self.ok(code=code, refactored=True)

    async def _explain(self, d: dict) -> dict:
        """
        Explain code step by step using LLM.
        """
        lang = d.get("language", "python")
        exp  = await self.ask_llm(
            f"Explain this {lang} code clearly and simply, step by step:\n{d.get('code', '')}"
        )
        return self.ok(explanation=exp)

    async def _review(self, d: dict) -> dict:
        """
        Review code for bugs, security issues, and improvements using LLM.
        """
        lang   = d.get("language", "python")
        review = await self.ask_llm(
            f"Code review this {lang} — list bugs, security issues, and improvements:\n{d.get('code', '')}"
        )
        return self.ok(review=review)

    async def _test(self, d: dict) -> dict:
        """
        Generate pytest tests for Python code, then optionally run them. Only supports Python.
        """
        code    = d.get("code", "")
        fn      = d.get("filename", "")
        lang    = d.get("language", "python")
        run     = d.get("run_tests", False)

        if lang != "python":
            return self.ok(
                tests=None,
                skipped=True,
                reason=f"Auto-test generation only supported for Python, not {lang}.",
            )

        prompt = (
            f"Write complete pytest unit tests for the following Python code.\n"
            f"- Use pytest fixtures where appropriate\n"
            f"- Test normal cases, edge cases, and error cases\n"
            f"- Do NOT import the module by relative path; mock external dependencies\n"
            f"- Return ONLY code in a single ```python block.\n\n"
            f"Code to test:\n```python\n{code}\n```"
        )

        test_code = await self.ask_llm(prompt)
        test_code = self._strip(test_code, "python")

        # Validate test syntax
        ok, err = self._py_syntax_check(test_code)
        if not ok:
            return self.ok(tests=test_code, valid=False, syntax_error=err, ran=False)

        # Save test file
        stem      = Path(fn).stem if fn else "module"
        test_fn   = f"test_{stem}.py"
        test_path = Path("workspace") / test_fn
        test_path.write_text(test_code)
        await self.report(f"Test file saved: workspace/{test_fn}")

        result = {"tests": test_code, "valid": True, "test_file": test_fn, "ran": False}

        # Optionally run tests with pytest
        if run:
            try:
                proc = subprocess.run(
                    ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"],
                    capture_output=True, text=True, timeout=60,
                    cwd=Path("workspace"),
                )
                result.update({
                    "ran":       True,
                    "passed":    proc.returncode == 0,
                    "stdout":    proc.stdout[-3000:],   # cap output length
                    "stderr":    proc.stderr[-1000:],
                    "returncode": proc.returncode,
                })
                await self.report(
                    f"Tests {'PASSED' if proc.returncode == 0 else 'FAILED'} "
                    f"(exit {proc.returncode})"
                )
            except subprocess.TimeoutExpired:
                result.update({"ran": True, "passed": False, "stdout": "", "stderr": "Timeout after 60s"})
            except FileNotFoundError:
                result.update({"ran": False, "stderr": "pytest not found in environment"})

        return self.ok(**result)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _llm_fix_code(self, code: str, error: str, lang: str = "python") -> str:
        """
        Ask the LLM to fix code given an error message.
        """
        prompt = (
            f"Fix this {lang} code.\n"
            f"Error: {error}\n\n"
            f"Code:\n```{lang}\n{code}\n```\n"
            f"Return ONLY the fixed code in a single ```{lang} block. No explanations."
        )
        fixed = await self.ask_llm(prompt)
        return self._strip(fixed, lang)

    @staticmethod
    def _py_syntax_check(code: str) -> tuple[bool, str]:
        """
        Check Python syntax. Returns (is_valid, error_message).
        """
        if not code or not code.strip():
            return False, "Empty code"
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    @staticmethod
    def _default_ext(lang: str) -> str:
        """
        Return the default file extension for a given language.
        """
        return {
            "python":     ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "rust":       ".rs",
            "go":         ".go",
            "java":       ".java",
            "bash":       ".sh",
            "html":       ".html",
            "css":        ".css",
            "c":          ".c",
            "c++":        ".cpp",
            "cpp":        ".cpp",
        }.get(lang, ".py")

    def _strip(self, text: str, lang: str = "") -> str:
        """
        Extract clean code from LLM output, removing prose and markdown fences.
        """
        if not isinstance(text, str):
            return ""

        # Try to extract a fenced block matching the target language first
        if lang:
            m = re.search(rf"```{re.escape(lang)}\n(.*?)```", text, re.DOTALL)
            if m:
                return m.group(1).strip()

        # Fall back to any fenced block
        m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()

        # Multiple blocks — join them
        blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        if blocks:
            return "\n\n".join(b.strip() for b in blocks)

        # No fences — strip leading prose until first recognisable code token
        starts = _LANG_STARTS.get(lang, _DEFAULT_STARTS)
        lines  = text.split("\n")
        start  = 0
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped and (stripped.startswith(starts) or stripped[0] == "#"):
                start = i
                break

        return "\n".join(lines[start:]).strip()