"""
Debugger Agent — Real code analysis + optimization + LLM-powered fix.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOT just an LLM wrapper anymore. Does REAL analysis:
  - AST parsing for imports, complexity, dead code
  - Pattern-based error detection (no LLM needed)
  - Memory/speed optimization suggestions
  - Fix validation (run the fixed code, verify it works)
  - Root-cause analysis using causal reasoning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import re, ast, sys, subprocess, traceback, tempfile
from pathlib import Path
from base_agent import BaseAgent

# ── Common Error Patterns (no LLM needed) ─────────────────────
_ERROR_PATTERNS = {
    r"NameError: name '(\w+)' is not defined": (
        "Variable '{0}' is used before being defined. "
        "Check spelling or add import/assignment before this line."
    ),
    r"ImportError: No module named '(\w+)'": (
        "Module '{0}' is not installed. Run: pip install {0}"
    ),
    r"IndentationError": (
        "Python indentation is wrong. Check tabs vs spaces — use 4 spaces consistently."
    ),
    r"KeyError: '?(\w+)'?": (
        "Dictionary doesn't have key '{0}'. Use .get('{0}', default) instead."
    ),
    r"TypeError: .* argument": (
        "Function called with wrong number/type of arguments. Check function signature."
    ),
    r"IndexError: list index out of range": (
        "Trying to access list index that doesn't exist. Check list length first."
    ),
    r"AttributeError: '(\w+)' object has no attribute '(\w+)'": (
        "Object of type '{0}' doesn't have attribute '{1}'. Check class definition."
    ),
    r"ZeroDivisionError": (
        "Division by zero. Add a check: if divisor != 0 before dividing."
    ),
    r"FileNotFoundError: .* '(.*)'": (
        "File '{0}' not found. Check the path exists, use os.path.exists() before opening."
    ),
    r"RecursionError": (
        "Infinite recursion detected. Add a proper base case to stop recursion."
    ),
    r"SyntaxError: (.*)" : (
        "Syntax error: {0}. Check for missing colons, brackets, or quotes."
    ),
}


class DebuggerAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("DebuggerAgent", eb, state)
        self._fix_history = []  # Track what we've fixed and whether it worked

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "analyze")
        await self.report(f"Debugger [{action}]")
        if action == "analyze":    return await self._analyze(d)
        if action == "fix":        return await self._fix(d)
        if action == "trace":      return await self._parse_trace(d.get("trace",""))
        if action == "root_cause": return await self._root_cause(d)
        if action == "optimize":   return await self._optimize(d)
        if action == "inspect":    return await self._inspect_file(d)
        if action == "validate":   return await self._validate_code(d)
        return await self._analyze(d)

    # ══════════════════════════════════════════════════════════════
    # ANALYZE — Real AST + pattern analysis FIRST, then LLM
    # ══════════════════════════════════════════════════════════════

    async def _analyze(self, d: dict) -> dict:
        error = d.get("error", "")
        code  = d.get("code", "")
        filepath = d.get("file", "")

        findings = []

        # Step 1: Pattern-based error detection (FAST, no LLM)
        pattern_fix = self._match_error_pattern(error)
        if pattern_fix:
            findings.append({"source": "pattern", "fix": pattern_fix})

        # Step 2: AST analysis of code (REAL analysis, no LLM)
        if code:
            ast_report = self._ast_analyze(code)
            if ast_report["issues"]:
                findings.append({"source": "ast", "issues": ast_report["issues"]})

        # Step 3: Check if we've seen this error before
        past_fix = self._check_fix_history(error)
        if past_fix:
            findings.append({"source": "history", "past_fix": past_fix})

        # Step 4: LLM analysis for complex cases (only if pattern didn't solve it)
        llm_analysis = ""
        if not pattern_fix or len(error) > 200:
            prompt = f"""Analyze this error:
Error: {error[:500]}
Code: {code[:1500]}

Provide:
1. Root cause (one line)
2. Fix (code change needed)
3. Prevention tip"""
            llm_analysis = await self.ask_llm(prompt)
            findings.append({"source": "llm", "analysis": llm_analysis})

        return self.ok(
            analysis=llm_analysis if llm_analysis else pattern_fix,
            pattern_fix=pattern_fix,
            findings=findings,
            error=error
        )

    # ══════════════════════════════════════════════════════════════
    # FIX — Fix + validate (don't just trust LLM output)
    # ══════════════════════════════════════════════════════════════

    async def _fix(self, d: dict) -> dict:
        code  = d.get("code", "")
        error = d.get("error", "")

        fixed = await self.ask_llm(
            f"Fix this code. Error: {error}\n\nCode:\n{code[:2000]}\n\n"
            "Return ONLY the fixed code, no explanation."
        )

        # Validate: does the fixed code at least parse?
        validation = self._validate_syntax(fixed)

        if validation["valid"]:
            # Record successful fix
            self._fix_history.append({
                "error": error[:200], "fixed": True,
                "strategy": "llm_fix"
            })
            return self.ok(fixed_code=fixed, original_error=error,
                          validation=validation)
        else:
            # LLM produced broken code — try again with the syntax error
            retry = await self.ask_llm(
                f"Your previous fix had a syntax error: {validation['error']}\n"
                f"Original code:\n{code[:1500]}\n"
                f"Original error: {error}\n\n"
                "Return ONLY correct, working code."
            )
            validation2 = self._validate_syntax(retry)
            if validation2["valid"]:
                self._fix_history.append({
                    "error": error[:200], "fixed": True,
                    "strategy": "llm_retry"
                })
                return self.ok(fixed_code=retry, original_error=error,
                              validation=validation2, retried=True)
            else:
                self._fix_history.append({
                    "error": error[:200], "fixed": False,
                    "strategy": "failed"
                })
                return self.ok(
                    fixed_code=code, original_error=error,
                    validation=validation2, 
                    warning="Fix failed validation. Original code returned."
                )

    # ══════════════════════════════════════════════════════════════
    # OPTIMIZE — Real code optimization (AST-based)
    # ══════════════════════════════════════════════════════════════

    async def _optimize(self, d: dict) -> dict:
        """Analyze code for optimization opportunities using AST."""
        code = d.get("code", "")
        filepath = d.get("file", "")

        if filepath and not code:
            fp = Path(filepath)
            if fp.exists():
                code = fp.read_text(errors="ignore")

        if not code:
            return self.ok(suggestions=[], error="No code provided")

        suggestions = []

        # AST-based optimization analysis
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return self.ok(suggestions=[f"Fix syntax error first: {e}"])

        for node in ast.walk(tree):
            # 1. Long functions (> 30 lines)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or 0) - node.lineno
                if length > 30:
                    suggestions.append({
                        "type": "complexity",
                        "line": node.lineno,
                        "message": f"Function '{node.name}()' is {length} lines. "
                                   f"Consider splitting into smaller functions.",
                    })

                # Nested loops (O(n²) or worse)
                loop_depth = self._count_loop_depth(node)
                if loop_depth >= 2:
                    suggestions.append({
                        "type": "performance",
                        "line": node.lineno,
                        "message": f"Function '{node.name}()' has {loop_depth} nested loops. "
                                   f"Consider using dict/set for O(1) lookups.",
                    })

            # 2. String concatenation in loops (use list + join instead)
            if isinstance(node, ast.AugAssign):
                if isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
                    suggestions.append({
                        "type": "performance",
                        "line": node.lineno,
                        "message": f"String += in loop at line {node.lineno}. "
                                   f"Use a list and ''.join() for better performance.",
                    })

            # 3. Bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                suggestions.append({
                    "type": "quality",
                    "line": node.lineno,
                    "message": "Bare 'except:' catches everything including KeyboardInterrupt. "
                               "Use 'except Exception:' instead.",
                })

            # 4. Global variable use
            if isinstance(node, ast.Global):
                suggestions.append({
                    "type": "quality",
                    "line": node.lineno,
                    "message": f"Global variables used. Consider passing as parameters instead.",
                })

        # 5. Check imports
        imports = self._analyze_imports(tree, code)
        suggestions.extend(imports)

        # LLM suggestions for deeper optimization (only if code is complex)
        if len(code) > 500:
            llm_tips = await self.ask_llm(
                f"Suggest 3 specific performance/memory optimizations for this code "
                f"(focus on algorithmic complexity, not style):\n\n{code[:2000]}"
            )
            suggestions.append({
                "type": "llm_optimization",
                "message": llm_tips
            })

        return self.ok(suggestions=suggestions, total=len(suggestions))

    # ══════════════════════════════════════════════════════════════
    # INSPECT — Deep file inspection
    # ══════════════════════════════════════════════════════════════

    async def _inspect_file(self, d: dict) -> dict:
        """Deep inspection of a Python file: AST, complexity, dependencies."""
        filepath = d.get("file", "")
        fp = Path(filepath)
        if not fp.exists():
            return self.ok(error=f"File not found: {filepath}")

        code = fp.read_text(errors="ignore")
        ast_report = self._ast_analyze(code)

        return self.ok(
            file=filepath,
            lines=len(code.splitlines()),
            size_bytes=len(code.encode()),
            **ast_report
        )

    # ══════════════════════════════════════════════════════════════
    # VALIDATE — Run code and check it works
    # ══════════════════════════════════════════════════════════════

    async def _validate_code(self, d: dict) -> dict:
        """Validate code by actually running it in a subprocess."""
        code = d.get("code", "")
        if not code:
            return self.ok(valid=False, error="No code provided")

        # Step 1: Syntax check
        syntax = self._validate_syntax(code)
        if not syntax["valid"]:
            return self.ok(valid=False, stage="syntax", error=syntax["error"])

        # Step 2: Actually run in subprocess (sandboxed by subprocess timeout)
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                tmp_path = f.name

            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path(".").resolve())
            )
            Path(tmp_path).unlink(missing_ok=True)

            if result.returncode == 0:
                return self.ok(valid=True, stage="execution",
                              output=result.stdout[:500])
            else:
                return self.ok(valid=False, stage="execution",
                              error=result.stderr[:500])
        except subprocess.TimeoutExpired:
            Path(tmp_path).unlink(missing_ok=True)
            return self.ok(valid=False, stage="timeout",
                          error="Code took >10s to run")
        except Exception as e:
            return self.ok(valid=False, stage="error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # EXISTING METHODS (improved)
    # ══════════════════════════════════════════════════════════════

    async def _parse_trace(self, trace: str) -> dict:
        lines  = trace.strip().splitlines()
        errors = [l for l in lines if "Error" in l or "Exception" in l]
        files  = re.findall(r'File "(.*?)", line (\d+)', trace)

        # Also pattern-match the error
        pattern_fix = ""
        if errors:
            pattern_fix = self._match_error_pattern(errors[-1])

        return self.ok(
            error_lines=errors,
            file_locations=files,
            summary=errors[-1] if errors else "No error found",
            pattern_fix=pattern_fix
        )

    async def _root_cause(self, d: dict) -> dict:
        error = d.get("error", "")
        logs = d.get("logs", "")

        # Use reasoning engine for causal analysis if available
        try:
            from reasoning_engine import ReasoningEngine
            engine = ReasoningEngine(self.event_bus if hasattr(self, 'orc') else None)
            causal = await engine.analyze_causality(error, context=logs[:1000])
            return self.ok(
                root_cause=causal.get("root_cause", ""),
                chain=causal.get("chain", []),
                prevention=causal.get("prevention", ""),
                prediction=causal.get("prediction", ""),
            )
        except Exception:
            # Fallback to simple LLM analysis
            analysis = await self.ask_llm(
                f"Find the root cause of:\nError: {error}\n"
                f"Logs: {logs[:2000]}")
            return self.ok(root_cause=analysis)

    # ══════════════════════════════════════════════════════════════
    # INTERNAL: Real AST Analysis (no LLM)
    # ══════════════════════════════════════════════════════════════

    def _ast_analyze(self, code: str) -> dict:
        """Full AST analysis of Python code — REAL, no LLM."""
        report = {
            "issues": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "complexity_score": 0,  # 0=simple, 10=very complex
        }

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            report["issues"].append({"type": "syntax_error", "line": e.lineno, "msg": str(e)})
            return report

        complexity = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or 0) - node.lineno
                report["functions"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "length": length,
                    "args": len(node.args.args),
                })
                complexity += min(length / 10, 3)  # Long functions add complexity
                if length > 50:
                    report["issues"].append({
                        "type": "long_function",
                        "line": node.lineno,
                        "msg": f"'{node.name}()' is {length} lines"
                    })

            elif isinstance(node, ast.ClassDef):
                methods = [n for n in ast.walk(node)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                report["classes"].append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": len(methods),
                })

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = ""
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                else:
                    mod = ", ".join(a.name for a in node.names)
                report["imports"].append(mod)

            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                report["issues"].append({
                    "type": "bare_except",
                    "line": node.lineno,
                    "msg": "Bare except: catches everything"
                })

        report["complexity_score"] = min(10, round(complexity, 1))
        return report

    def _analyze_imports(self, tree: ast.Module, code: str) -> list:
        """Find unused imports."""
        issues = []
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names.append((name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names.append((name, node.lineno))

        # Check if each imported name is used in the code (crude but effective)
        for name, lineno in imported_names:
            # Count usage (excluding the import line itself)
            lines = code.splitlines()
            usage_count = 0
            for i, line in enumerate(lines, 1):
                if i == lineno:
                    continue
                if re.search(r'\b' + re.escape(name) + r'\b', line):
                    usage_count += 1
            if usage_count == 0:
                issues.append({
                    "type": "unused_import",
                    "line": lineno,
                    "message": f"Import '{name}' appears unused. Remove if not needed.",
                })
        return issues

    def _count_loop_depth(self, node) -> int:
        """Count max nested loop depth inside a function."""
        max_depth = 0

        def walk(n, depth):
            nonlocal max_depth
            if isinstance(n, (ast.For, ast.While)):
                depth += 1
                max_depth = max(max_depth, depth)
            for child in ast.iter_child_nodes(n):
                walk(child, depth)

        walk(node, 0)
        return max_depth

    def _match_error_pattern(self, error: str) -> str:
        """Match error against known patterns — instant fix, no LLM."""
        for pattern, fix_template in _ERROR_PATTERNS.items():
            m = re.search(pattern, error)
            if m:
                groups = m.groups()
                try:
                    return fix_template.format(*groups) if groups else fix_template
                except (IndexError, KeyError):
                    return fix_template
        return ""

    def _validate_syntax(self, code: str) -> dict:
        """Check if code is valid Python syntax."""
        try:
            ast.parse(code)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}

    def _check_fix_history(self, error: str) -> str:
        """Check if we've seen and fixed this error before."""
        err_words = set(error.lower().split()[:10])
        for past in reversed(self._fix_history[-30:]):
            past_words = set(past.get("error", "").lower().split()[:10])
            if len(err_words & past_words) >= 3 and past.get("fixed"):
                return f"Similar error fixed before using strategy: {past.get('strategy', '?')}"
        return ""
