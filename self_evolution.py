"""
Self Evolution Engine — AMRIT GODMODE ਦਾ ਦਿਲ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is the TRUE autonomous loop. It doesn't wait for instructions.
It continuously:
  1. ਆਪਣੇ ਆਪ ਨੂੰ ਚੈੱਕ ਕਰਦਾ — Self-analyzes code quality, bugs, TODOs
  2. ਕਮੀਆਂ ਲੱਭਦਾ — Finds weaknesses via testing + benchmarks
  3. ਆਪੇ ਠੀਕ ਕਰਦਾ — Self-fixes bugs & implements TODOs
  4. ਤੇਜ਼ ਬਣਾਉਂਦਾ — Benchmarks and optimizes slow paths
  5. ਨਵੀਆਂ ਖੋਜਾਂ ਸਿੱਖਦਾ — Researches new AI techniques
  6. ਟੈਸਟ ਕਰਦਾ — Runs tests before & after every change
  7. ਬੈਕਅੱਪ ਰੱਖਦਾ — Creates backups before any modification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import asyncio
import time
import json
import os
import sys
import subprocess
import ast
import shutil
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("SelfEvolution")

# ── Evolution Phases ──────────────────────────────────────────────
PHASE_ANALYZE  = "analyze"
PHASE_TEST     = "test"
PHASE_FIX      = "fix"
PHASE_OPTIMIZE = "optimize"
PHASE_RESEARCH = "research"
PHASE_LEARN    = "learn"

BACKUP_DIR = Path("workspace/evolution_backups")
EVOLUTION_LOG = Path("workspace/evolution_log.json")
LESSONS_FILE  = Path("workspace/evolution_lessons.json")
PENDING_FILE  = Path("workspace/pending_improvements.json")


class SelfEvolution:
    """
    True autonomous self-improvement engine — UPGRADED.
    
    New capabilities:
      - Actually APPLIES learned lessons (not just records them)
      - Causal analysis — tracks which fixes broke/helped what
      - Skips useless cycles (if nothing to fix, don't waste LLM calls)
      - Failure pattern memory integration (never repeat same mistake)
      - Records before/after metrics for every change
    """

    def __init__(self, orchestrator):
        self.orc = orchestrator
        self.cycle = 0
        self.running = False
        self._log = []
        self._load_log()
        self._scores = {}        # file → quality score (0-1)
        self._benchmarks = {}    # operation → seconds
        self._lessons = self._load_lessons()  # Applied lessons
        self._prev_test_results = None  # Track before/after
        self._blacklist: set = set()          # Files that caused regression — never touch
        self._fix_history: dict = {}           # file → list of cycle numbers when fixed
        self._consec_fail: dict = {}           # file → consecutive failure count
        self._refactor_history: dict = {}      # file → list of cycle numbers when refactored
        self._quality_trend: list = []         # avg quality per cycle (tracks improvement)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _load_lessons(self) -> list:
        """Load learned lessons from disk."""
        if LESSONS_FILE.exists():
            try:
                return json.loads(LESSONS_FILE.read_text())
            except Exception:
                pass
        return []

    def _save_lessons(self):
        """Persist lessons to disk."""
        LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        LESSONS_FILE.write_text(json.dumps(self._lessons[-100:], indent=2, default=str))

    def _load_log(self):
        if EVOLUTION_LOG.exists():
            try:
                self._log = json.loads(EVOLUTION_LOG.read_text())
            except Exception:
                self._log = []

    def _save_log(self):
        EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        EVOLUTION_LOG.write_text(json.dumps(self._log[-200:], indent=2, default=str))

    def _record(self, phase, action, result, success=True):
        entry = {
            "cycle": self.cycle,
            "phase": phase,
            "action": action,
            "success": success,
            "result": str(result)[:500],
            "timestamp": datetime.now().isoformat()
        }
        self._log.append(entry)
        icon = "✅" if success else "❌"
        logger.info(f"[Cycle {self.cycle}] {icon} {phase}: {action}")
        if len(self._log) % 5 == 0:
            self._save_log()

    # ══════════════════════════════════════════════════════════════
    # MAIN LOOP — ਇਹ ਹੈ ਅਸਲੀ ਆਟੋਨੋਮਸ ਲੂਪ
    # ══════════════════════════════════════════════════════════════

    async def run(self, max_cycles: int = 0, single_task: str = None):
        """
        Run the self-evolution loop.
        - max_cycles=0 means infinite (true autonomous)
        - single_task: if given, execute that task first, then self-improve
        """
        self.running = True
        logger.info("═" * 60)
        logger.info("  ⚡ SELF-EVOLUTION ENGINE STARTED / ਸੈਲਫ-ਐਵੋਲੂਸ਼ਨ ਸ਼ੁਰੂ")
        logger.info("═" * 60)

        # Phase 0: If user gave a task, do it first
        if single_task:
            await self._execute_user_task(single_task)

        while self.running:
            self.cycle += 1
            if max_cycles and self.cycle > max_cycles:
                logger.info(f"Reached max cycles ({max_cycles}). Stopping.")
                break

            logger.info(f"\n{'━' * 50}")
            logger.info(f"  🔄 EVOLUTION CYCLE {self.cycle}")
            logger.info(f"{'━' * 50}")

            try:
                # Phase 1: Self-Analyze — ਆਪਣੇ ਕੋਡ ਦੀ ਜਾਂਚ
                issues = await self._phase_analyze()

                # Phase 2: Self-Test — ਸਭ ਕੁਝ ਟੈਸਟ ਕਰੋ
                test_results = await self._phase_test()

                # SMART: Separate critical (auto-fixable) from advisory issues
                FIXABLE_TYPES = {"syntax_error", "not_implemented", "empty_file", "bare_except", "todo", "lint_errors"}
                ADVISORY_TYPES = {"long_function"}
                critical_issues = [i for i in issues
                                   if any(x["type"] in FIXABLE_TYPES for x in i["issues"])]
                sum(1 for i in issues
                                     if all(x["type"] in ADVISORY_TYPES for x in i["issues"]))
                has_fixable = (bool(critical_issues) or
                               bool(test_results.get("failures")) or
                               bool(test_results.get("import_errors")))

                # Phase 3: Self-Fix — ਕਮੀਆਂ ਠੀਕ ਕਰੋ (only if fixable issues exist)
                if has_fixable:
                    self._prev_test_results = test_results  # Record "before"
                    fixed_count = await self._phase_fix(critical_issues, test_results)
                    # Only re-test if something was actually fixed
                    if fixed_count > 0:
                        post_test = await self._phase_test()
                        self._verify_fix_impact(test_results, post_test)
                    else:
                        self._record("verify", "fix_impact", "nothing_to_fix")

                # Phase 3b: Self-Refactor — long functions ਨੂੰ split ਕਰੋ (1 file per cycle)
                advisory_issues = [i for i in issues
                                   if all(x["type"] in ADVISORY_TYPES for x in i["issues"])]
                if advisory_issues:
                    await self._phase_refactor(advisory_issues)
                elif not has_fixable:
                    logger.info("  ✨ No issues — system is clean!")

                # Phase 4: Self-Optimize — ਤੇਜ਼ ਬਣਾਓ
                await self._phase_optimize()

                # Phase 5: Research + Queue Improvements — ਖੋਜੋ ਅਤੇ ਕਤਾਰ ਵਿੱਚ ਰੱਖੋ
                if self.cycle % 3 == 0:
                    await self._phase_research()

                # Phase 6: Learn + APPLY pending improvements — ਸਿੱਖੋ ਤੇ ਲਾਗੂ ਕਰੋ
                await self._phase_learn()

                # Phase 7: Punjabi Model Training — ਪੰਜਾਬੀ ਮਾਡਲ ਟ੍ਰੇਨਿੰਗ
                # Every 10 cycles, run one LoRA training cycle
                if self.cycle % 10 == 0:
                    await self._phase_train_punjabi()

                # Print cycle summary
                self._print_cycle_summary()

            except Exception as e:
                logger.error(f"Evolution cycle {self.cycle} error: {e}")
                self._record("error", f"cycle_{self.cycle}", str(e), success=False)

            # Pause between cycles (give system breathing room)
            await asyncio.sleep(2)

        self._save_log()
        logger.info("Self-Evolution stopped.")

    def stop(self):
        self.running = False

    # ══════════════════════════════════════════════════════════════
    # PHASE 1: SELF-ANALYZE — ਆਪਣੇ ਆਪ ਦਾ ਵਿਸ਼ਲੇਸ਼ਣ
    # ══════════════════════════════════════════════════════════════

    async def _phase_analyze(self) -> list:
        """Scan all Python files for issues: syntax errors, TODOs, empty files, bad patterns."""
        logger.info("🔍 Phase 1: Self-Analysis / ਕੋਡ ਦੀ ਜਾਂਚ")
        issues = []
        # ਇਹ ਫਾਈਲਾਂ ਕਦੇ ਨਾ ਛੋਹੋ — core files that must not be auto-modified
        PROTECTED = {"self_evolution.py", "upgrade_agent.py", "orchestrator.py",
                     "base_agent.py", "event_bus.py", "config_loader.py", "main.py"}
        py_files = [f for f in Path(".").glob("*.py") if f.name not in PROTECTED]

        for fp in py_files:
            try:
                code = fp.read_text(errors="ignore")
                file_issues = []

                # Check 1: Syntax errors
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    file_issues.append({"type": "syntax_error", "detail": str(e)})

                # Check 2: Empty or stub files
                if len(code.strip()) < 20:
                    file_issues.append({"type": "empty_file", "detail": "File is empty or stub"})

                # Check 3: TODOs and NotImplementedError
                for i, line in enumerate(code.splitlines(), 1):
                    stripped = line.lstrip()
                    # Only count real TODO/FIXME comments (# TODO), not string mentions
                    if stripped.startswith("#") and ("TODO" in stripped or "FIXME" in stripped):
                        file_issues.append({"type": "todo", "line": i, "detail": stripped})
                    if "NotImplementedError" in line and "raise" in line:
                        file_issues.append({"type": "not_implemented", "line": i, "detail": line.strip()})

                # Check 4: Bare except clauses (code smell)
                bare_excepts = len([ln for ln in code.splitlines() if ln.strip() == "except:"])
                if bare_excepts > 0:
                    file_issues.append({"type": "bare_except", "detail": f"{bare_excepts} bare except clauses"})

                # Check 5: Functions longer than 50 lines
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        func_lines = (node.end_lineno or 0) - node.lineno
                        if func_lines > 50:
                            file_issues.append({"type": "long_function",
                                                "detail": f"{node.name}() is {func_lines} lines"})

                # Calculate quality score
                score = 1.0
                score -= len(file_issues) * 0.1
                score = max(0.0, min(1.0, score))
                self._scores[str(fp)] = score

                if file_issues:
                    issues.append({"file": str(fp), "issues": file_issues, "score": score})

            except Exception as e:
                issues.append({"file": str(fp), "issues": [{"type": "read_error", "detail": str(e)}]})

        # ── Ruff Lint Scan ────────────────────────────────────────
        ruff_issues = self._run_ruff_check()
        if ruff_issues:
            issues.append({
                "file": "__ruff__",
                "issues": [{"type": "lint_errors", "detail": f"{ruff_issues} ruff violations"}],
                "score": max(0.0, 1.0 - ruff_issues * 0.002),
            })

        total = len(py_files)
        bad = len(issues)
        self._record(PHASE_ANALYZE, f"scanned {total} files", f"{bad} files with issues")
        logger.info(f"  📊 {total} files scanned | {bad} with issues | "
                    f"avg score: {sum(self._scores.values()) / max(len(self._scores), 1):.2f}")

        return issues

    # ══════════════════════════════════════════════════════════════
    # PHASE 2: SELF-TEST — ਆਪਣੇ ਆਪ ਨੂੰ ਟੈਸਟ ਕਰੋ
    # ══════════════════════════════════════════════════════════════

    async def _phase_test(self) -> dict:
        """Run all tests and import checks."""
        logger.info("🧪 Phase 2: Self-Testing / ਟੈਸਟ ਚਲਾਓ")
        results = {"passed": 0, "failed": 0, "failures": [], "import_errors": []}

        # Test 1: Import every module
        py_files = [f.stem for f in Path(".").glob("*.py")
                    if f.name not in ("main.py", "self_evolution.py", "test_godmode.py",
                                      "test_security.py", "setup.py")]
        for mod in py_files:
            try:
                r = subprocess.run(
                    [sys.executable, "-c", f"import {mod}"],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(Path(".").resolve())
                )
                if r.returncode == 0:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    err_msg = r.stderr.strip().split("\n")[-1] if r.stderr else "unknown"
                    results["import_errors"].append({"module": mod, "error": err_msg})
            except subprocess.TimeoutExpired:
                results["import_errors"].append({"module": mod, "error": "timeout"})
            except Exception as e:
                results["import_errors"].append({"module": mod, "error": str(e)})

        # Test 2: Run existing test files
        test_files = list(Path(".").glob("test_*.py"))
        for tf in test_files:
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pytest", str(tf), "-x", "-q", "--tb=line"],
                    capture_output=True, text=True, timeout=30,
                    cwd=str(Path(".").resolve())
                )
                if r.returncode == 0:
                    results["passed"] += 1
                else:
                    results["failures"].append({"test": str(tf),
                                                "output": (r.stdout + r.stderr)[-500:]})
            except Exception as e:
                results["failures"].append({"test": str(tf), "output": str(e)})

        self._record(PHASE_TEST, f"tested {len(py_files)} modules",
                     f"passed={results['passed']} failed={results['failed']}")
        logger.info(f"  ✅ Passed: {results['passed']} | ❌ Failed: {results['failed']} | "
                    f"Import errors: {len(results['import_errors'])}")
        return results

    # ══════════════════════════════════════════════════════════════
    # PHASE 3: SELF-FIX — ਆਪੇ ਠੀਕ ਕਰੋ
    # ══════════════════════════════════════════════════════════════

    async def _phase_fix(self, issues: list, test_results: dict) -> int:
        """Fix discovered issues — with persistence check, blacklist, verify, root-cause, escalation.
        Returns number of files fixed."""
        logger.info("🔧 Phase 3: Self-Fix / ਕਮੀਆਂ ਠੀਕ ਕਰੋ")
        coder = self.orc.get_agent("coder")
        if not coder:
            self._record(PHASE_FIX, "skip", "no coder agent", success=False)
            return 0

        fixed_count = 0
        import_errors = test_results.get("import_errors", [])

        # ── ROOT CAUSE: if 10+ import errors share a common missing dep ──────
        if len(import_errors) >= 10:
            common = self._detect_common_root_cause(import_errors)
            if common:
                logger.warning(f"  ⚠️  ROOT CAUSE: {common}")
                self._record(PHASE_FIX, "root_cause", common, success=False)

        # ── Fix syntax errors / not_implemented / bare_except / todo (max 5 per cycle) ──
        fixable = [i for i in issues
                   if any(x["type"] in ("syntax_error", "not_implemented", "empty_file",
                                        "bare_except", "todo")
                          for x in i["issues"])
                   and i["file"] not in self._blacklist][:5]

        # ── Quick-fix bare excepts without LLM (safe transformation) ─────────
        for item in list(fixable):
            fp = Path(item["file"])
            bare_issues = [x for x in item["issues"] if x["type"] == "bare_except"]
            if bare_issues and fp.exists():
                code = fp.read_text(errors="ignore")
                new_code = code.replace("\nexcept:\n", "\nexcept Exception:\n")
                if new_code != code:
                    self._backup(fp)
                    fp.write_text(new_code)
                    fixed_count += 1
                    self._record(PHASE_FIX, f"fixed bare_except {fp.name}",
                                 "replaced except: with except Exception:")
                    logger.info(f"  ✅ {fp.name}: bare except → except Exception")
                    # Remove from fixable if that was the only issue
                    other_issues = [x for x in item["issues"] if x["type"] != "bare_except"]
                    if not other_issues:
                        fixable.remove(item)

        for item in fixable:
            fp = Path(item["file"])
            fname = fp.name
            if not fp.exists():
                continue

            # ── ESCALATION: 5+ consecutive failures ───────────────────────────
            if self._consec_fail.get(fname, 0) >= 5:
                logger.error(f"  🚨 HUMAN REVIEW NEEDED: {fname} — automated fixing is not resolving this issue.")
                self._record(PHASE_FIX, f"escalate {fname}",
                             f"5+ consecutive failures: {item['issues'][0]['detail']}", success=False)
                continue

            # ── PERSISTENCE CHECK: fixed 3+ times recently ────────────────────
            recent_fixes = self._fix_history.get(fname, [])
            if len([c for c in recent_fixes if self.cycle - c <= 3]) >= 3:
                logger.warning(f"  ⚠️  PERSISTENCE ISSUE: {fname} fixed 3+ times but bug returns — skipping")
                self._record(PHASE_FIX, f"skip_persistent {fname}",
                             "fix not sticking — write mechanism suspect", success=False)
                continue

            code = fp.read_text(errors="ignore")
            issue_desc = "; ".join(x["detail"] for x in item["issues"][:3])
            mtime_before = fp.stat().st_mtime
            self._backup(fp)

            try:
                result = await coder.execute({
                    "name": f"Self-fix {fname}",
                    "data": {
                        "action": "fix",
                        "code": code[:3000],
                        "error": f"Issues found: {issue_desc}. Fix all issues. "
                                 "Keep all existing functionality. Return ONLY the fixed code."
                    }
                })
                new_code = result.get("code", "")
                if new_code and len(new_code) > 20:
                    try:
                        ast.parse(new_code)
                        fp.write_text(new_code)
                        # ── WRITE VERIFICATION ────────────────────────────────
                        if fp.stat().st_mtime == mtime_before:
                            logger.error(f"  ❌ WRITE FAILED: {fname} not modified on disk")
                            self._record(PHASE_FIX, f"write_failed {fname}",
                                         "file mtime unchanged after write", success=False)
                        else:
                            fixed_count += 1
                            self._fix_history.setdefault(fname, []).append(self.cycle)
                            self._consec_fail[fname] = 0
                            self._record(PHASE_FIX, f"fixed {fname}", issue_desc)
                    except SyntaxError:
                        self._record(PHASE_FIX, f"fix {fname}",
                                     "LLM produced invalid syntax", success=False)
                        self._restore(fp)
                        self._consec_fail[fname] = self._consec_fail.get(fname, 0) + 1
            except Exception as e:
                self._record(PHASE_FIX, f"fix {fname}", str(e), success=False)
                self._restore(fp)
                self._consec_fail[fname] = self._consec_fail.get(fname, 0) + 1

        # ── Fix import errors (max 4 per cycle) ──────────────────────────────
        for ie in import_errors[:4]:
            mod = ie["module"]
            err = ie["error"]
            fp = Path(f"{mod}.py")
            fname = fp.name
            if not fp.exists() or fname in self._blacklist:
                continue

            if self._consec_fail.get(fname, 0) >= 5:
                logger.error(f"  🚨 HUMAN REVIEW NEEDED: {fname} — {err}")
                continue

            recent_fixes = self._fix_history.get(fname, [])
            if len([c for c in recent_fixes if self.cycle - c <= 3]) >= 3:
                logger.warning(f"  ⚠️  PERSISTENCE ISSUE: {fname} — skipping")
                continue

            code = fp.read_text(errors="ignore")
            mtime_before = fp.stat().st_mtime
            self._backup(fp)

            try:
                result = await coder.execute({
                    "name": f"Fix import error in {mod}",
                    "data": {
                        "action": "fix",
                        "code": code[:3000],
                        "error": f"Import error: {err}. Fix the import issue. Return ONLY fixed code."
                    }
                })
                new_code = result.get("code", "")
                if new_code and len(new_code) > 20:
                    try:
                        ast.parse(new_code)
                        fp.write_text(new_code)
                        if fp.stat().st_mtime == mtime_before:
                            logger.error(f"  ❌ WRITE FAILED: {fname}")
                        else:
                            fixed_count += 1
                            self._fix_history.setdefault(fname, []).append(self.cycle)
                            self._consec_fail[fname] = 0
                            self._record(PHASE_FIX, f"fixed import {mod}", err)
                    except SyntaxError:
                        self._restore(fp)
                        self._consec_fail[fname] = self._consec_fail.get(fname, 0) + 1
            except Exception:
                self._restore(fp)
                self._consec_fail[fname] = self._consec_fail.get(fname, 0) + 1

        # ── Ruff auto-fix for lint_errors ─────────────────────────────
        lint_items = [i for i in issues if any(x["type"] == "lint_errors" for x in i["issues"])]
        if lint_items:
            ruff_fixed = self._run_ruff_fix()
            fixed_count += min(ruff_fixed, 1)  # count as 1 bulk fix

        logger.info(f"  🔧 Fixed {fixed_count} files this cycle")
        if self._blacklist:
            logger.info(f"  ⛔ Blacklisted (skipped): {', '.join(self._blacklist)}")
        return fixed_count

    def _detect_common_root_cause(self, import_errors: list) -> str:
        """Check if many import errors share a common root cause."""
        from collections import Counter
        words = []
        for ie in import_errors:
            words += ie.get("error", "").lower().split()
        noise = {"no", "module", "named", "cannot", "import", "error", "the", "a", "in", "from"}
        meaningful = [(w, c) for w, c in Counter(words).most_common(5)
                      if w not in noise and len(w) > 3]
        if meaningful and meaningful[0][1] >= len(import_errors) // 2:
            w, c = meaningful[0]
            return f"Likely missing dependency: '{w}' appears in {c}/{len(import_errors)} errors"
        return ""

    def _run_ruff_check(self) -> int:
        """Run ruff linter and return count of violations."""
        import subprocess
        try:
            result = subprocess.run(
                ["ruff", "check", ".", "--select=E,F",
                 "--ignore=E501,F401,F811,E402",
                 "--exclude=generated_test,workspace",
                 "--output-format=json"],
                capture_output=True, text=True, timeout=60,
                cwd=str(Path(self.orc.workspace if hasattr(self.orc, 'workspace') else '.').resolve())
            )
            if result.stdout.strip():
                import json as _json
                violations = _json.loads(result.stdout)
                count = len(violations)
                if count:
                    logger.info(f"  🔍 Ruff found {count} lint violations")
                return count
        except FileNotFoundError:
            logger.debug("  ruff not installed — skipping lint check")
        except Exception as e:
            logger.debug(f"  ruff check failed: {e}")
        return 0

    def _run_ruff_fix(self) -> int:
        """Run ruff --fix and return count of fixed violations."""
        import subprocess
        before = self._run_ruff_check()
        if before == 0:
            return 0
        try:
            subprocess.run(
                ["ruff", "check", ".", "--fix",
                 "--select=E,F",
                 "--ignore=E501,F401,F811,E402",
                 "--exclude=generated_test,workspace"],
                capture_output=True, text=True, timeout=60,
                cwd=str(Path(self.orc.workspace if hasattr(self.orc, 'workspace') else '.').resolve())
            )
        except Exception as e:
            logger.debug(f"  ruff fix failed: {e}")
            return 0
        after = self._run_ruff_check()
        fixed = before - after
        if fixed > 0:
            logger.info(f"  ✅ Ruff auto-fixed {fixed} violations ({after} remaining)")
            self._record(PHASE_FIX, "ruff_autofix", f"fixed {fixed}, remaining {after}")
        return fixed

    # ══════════════════════════════════════════════════════════════
    # PHASE 3b: SELF-REFACTOR — long functions ਨੂੰ split ਕਰੋ
    # ══════════════════════════════════════════════════════════════

    async def _phase_refactor(self, advisory_issues: list):
        """Refactor ONE long function at a time using AST extraction — function-by-function."""
        logger.info("\u2702\ufe0f  Phase 3b: Self-Refactor / \u0a32\u0a70\u0a2c\u0a47 \u0a2b\u0a70\u0a15\u0a38\u0a3c\u0a28 \u0a1b\u0a4b\u0a1f\u0a47 \u0a15\u0a30\u0a4b")
        coder = self.orc.get_agent("coder")
        if not coder:
            logger.info("  \u26a0\ufe0f  No coder agent \u2014 skipping refactor")
            return

        # Collect all individual long functions across all advisory files,
        # skip files/functions recently attempted (success or fail)
        SKIP_CYCLES = 5  # Don't retry the same function for 5 cycles
        candidates = []  # list of (fp, func_name, func_lines)
        for item in advisory_issues:
            fp = Path(item["file"])
            if str(fp) in self._blacklist or not fp.exists():
                continue
            for issue in item["issues"]:
                if issue["type"] != "long_function":
                    continue
                # detail format: "funcname() is N lines" or "funcname()=NL"
                detail = issue.get("detail", "")
                func_name = detail.split("(")[0].strip()
                key = f"{fp.name}::{func_name}"
                recent = [c for c in self._refactor_history.get(key, [])
                          if self.cycle - c <= SKIP_CYCLES]
                if not recent:
                    try:
                        lines = int(detail.split(" is ")[-1].split(" ")[0])
                    except Exception:
                        lines = 0
                    candidates.append((fp, func_name, lines))

        if not candidates:
            logger.info("  ⏭  No refactor candidates this cycle")
            return

        # Sort by lines — prefer 50-150 line functions, pick longest for max impact
        viable = [(fp, fn, fl) for fp, fn, fl in candidates if fl >= 50]
        if not viable:
            logger.info("  ⏭  No refactor candidates >= 50 lines this cycle")
            return

        # Pick the longest viable function for maximum score impact
        fp, func_name, func_lines = max(viable, key=lambda x: x[2])
        logger.info(f"  \u2702\ufe0f  {fp.name}::{func_name}() ({func_lines} lines) \u2014 extracting & refactoring")

        code = fp.read_text(errors="ignore")
        func_src = self._extract_function_source(code, func_name)
        if not func_src:
            logger.warning(f"  \u26a0\ufe0f  Could not extract {func_name}() \u2014 skipping")
            self._refactor_history.setdefault(f"{fp.name}::{func_name}", []).append(self.cycle)
            return

        self._backup(fp)
        key = f"{fp.name}::{func_name}"

        MAX_RETRIES = 3  # 2× 7B, final attempt → 32B escalation
        base_instructions = (
            f"This function is {func_lines} lines \u2014 too long. "
            "Split it into smaller private helper functions (max 40 lines each). "
            "Keep the original function signature and return value identical. "
            "Extract logical sub-steps into well-named helpers prefixed with _. "
            "Return ONLY the refactored Python functions (original + new helpers). "
            "Do NOT include the rest of the file."
        )

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                instructions = base_instructions
                if last_error:
                    instructions = (
                        f"PREVIOUS ATTEMPT FAILED with: {last_error}\n"
                        "Fix the syntax error and try again. "
                        "Make sure all brackets, parentheses, colons and indentation are correct.\n\n"
                        + base_instructions
                    )

                # Escalate to 32B on final attempt (7B ਫੇਲ੍ਹ → 32B ਕੋਲ ਭੇਜੋ)
                category = "deep" if attempt == MAX_RETRIES else "refactor"
                if attempt == MAX_RETRIES:
                    logger.info(f"  \U0001f9e0 7B ਫੇਲ੍ਹ — Qwen3-32B ਨਾਲ ਕੋਸ਼ਿਸ਼ ({func_lines} ਲਾਈਨਾਂ)...")

                result = await coder.execute({
                    "name": f"Refactor {func_name} in {fp.name}",
                    "data": {
                        "action": "refactor",
                        "code": func_src,
                        "category": category,
                        "error": instructions,
                    }
                })
                new_funcs = result.get("code", "").strip()

                # Validate: must be parseable and contain the original function name.
                if not new_funcs or len(new_funcs) < len(func_src) * 0.4 or func_name not in new_funcs:
                    last_error = f"Response too short or missing {func_name}"
                    if attempt < MAX_RETRIES:
                        logger.info(f"  \u26a0\ufe0f  Attempt {attempt}: {last_error} \u2014 retrying")
                        continue
                    logger.warning(f"  \u26a0\ufe0f  {last_error} after {MAX_RETRIES} attempts \u2014 skipping")
                    self._restore(fp)
                    self._refactor_history.setdefault(key, []).append(self.cycle)
                    return

                try:
                    ast.parse(new_funcs)
                except SyntaxError as e:
                    last_error = str(e)
                    if attempt < MAX_RETRIES:
                        logger.info(f"  \u26a0\ufe0f  Attempt {attempt}: syntax error: {e} \u2014 retrying with feedback")
                        continue
                    logger.warning(f"  \u274c LLM syntax error after {MAX_RETRIES} attempts: {e}")
                    self._restore(fp)
                    self._refactor_history.setdefault(key, []).append(self.cycle)
                    return

                # Stitch: replace old function body in file with new functions
                new_code = self._replace_function_in_source(code, func_name, func_src, new_funcs)
                if new_code and new_code != code:
                    try:
                        ast.parse(new_code)  # Validate whole file
                    except SyntaxError as e:
                        last_error = f"Full-file syntax error after stitch: {e}"
                        if attempt < MAX_RETRIES:
                            logger.info(f"  \u26a0\ufe0f  Attempt {attempt}: {last_error} \u2014 retrying")
                            continue
                        logger.warning(f"  \u274c {last_error}")
                        self._restore(fp)
                        self._refactor_history.setdefault(key, []).append(self.cycle)
                        return
                    fp.write_text(new_code)
                    self._refactor_history.setdefault(key, []).append(self.cycle)
                    self._fix_history.setdefault(fp.name, []).append(self.cycle)
                    self._scores[str(fp)] = min(1.0, self._scores.get(str(fp), 0.9) + 0.05)
                    self._record("refactor", f"split {fp.name}::{func_name}",
                                 f"{func_lines} lines split (attempt {attempt})", success=True)
                    logger.info(f"  \u2705 {fp.name}::{func_name}() refactored successfully"
                                + (f" (attempt {attempt})" if attempt > 1 else ""))
                    return
                else:
                    last_error = "Stitch produced no changes"
                    if attempt < MAX_RETRIES:
                        logger.info(f"  \u26a0\ufe0f  Attempt {attempt}: stitch failed \u2014 retrying")
                        continue
                    logger.warning(f"  \u2755 Stitch failed for {func_name} after {MAX_RETRIES} attempts")
                    self._restore(fp)
                    self._refactor_history.setdefault(key, []).append(self.cycle)
                    return

            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    logger.info(f"  \u26a0\ufe0f  Attempt {attempt}: error: {e} \u2014 retrying")
                    continue
                logger.error(f"  \u274c Refactor error after {MAX_RETRIES} attempts: {e}")
                self._restore(fp)
                self._refactor_history.setdefault(key, []).append(self.cycle)

    def _extract_function_source(self, code: str, func_name: str) -> str:
        """Extract a single function's source code using AST line numbers."""
        try:
            tree = ast.parse(code)
            lines = code.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        start = node.lineno - 1
                        end = node.end_lineno
                        return "\n".join(lines[start:end])
        except Exception:
            pass
        return ""

    def _replace_function_in_source(self, code: str, func_name: str,
                                    old_func_src: str, new_funcs_src: str) -> str:
        """Replace the old function in the full source with new refactored functions."""
        try:
            tree = ast.parse(code)
            lines = code.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        start = node.lineno - 1
                        end = node.end_lineno
                        # Preserve original indentation level
                        indent = len(lines[start]) - len(lines[start].lstrip())
                        indent_str = " " * indent
                        # Re-indent new functions to match
                        new_lines = []
                        for line in new_funcs_src.splitlines():
                            if line.strip():
                                new_lines.append(indent_str + line.lstrip() if not line.startswith(indent_str) else line)
                            else:
                                new_lines.append("")
                        replaced = lines[:start] + new_lines + lines[end:]
                        return "\n".join(replaced)
        except Exception:
            pass
        return ""

    # ══════════════════════════════════════════════════════════════
    # PHASE 4: SELF-OPTIMIZE — ਤੇਜ਼ ਬਣਾਓ
    # ══════════════════════════════════════════════════════════════

    async def _phase_optimize(self):
        """Benchmark key operations, find slow paths, optimize."""
        logger.info("⚡ Phase 4: Self-Optimize / ਤੇਜ਼ ਬਣਾਓ")

        # Benchmark 1: Module import times
        slow_imports = []
        key_modules = ["orchestrator", "llm_router", "goal_parser", "autonomy_loop",
                       "base_agent", "coder_agent", "planner_agent"]
        for mod in key_modules:
            t0 = time.perf_counter()
            try:
                subprocess.run(
                    [sys.executable, "-c", f"import {mod}"],
                    capture_output=True, text=True, timeout=5,
                    cwd=str(Path(".").resolve())
                )
                elapsed = time.perf_counter() - t0
                self._benchmarks[f"import_{mod}"] = elapsed
                if elapsed > 1.0:
                    slow_imports.append({"module": mod, "time": round(elapsed, 3)})
            except Exception:
                pass

        # Benchmark 2: Goal parsing speed (no LLM, rules only)
        t0 = time.perf_counter()
        try:
            subprocess.run(
                [sys.executable, "-c",
                 "import asyncio; from goal_parser import GoalParser; "
                 "gp = GoalParser(); gp._use_llm = False; "
                 "print(asyncio.run(gp.parse('write a punjabi poem')))"],
                capture_output=True, text=True, timeout=5,
                cwd=str(Path(".").resolve())
            )
            parse_time = time.perf_counter() - t0
            self._benchmarks["goal_parse_rules"] = parse_time
        except Exception:
            parse_time = -1

        self._record(PHASE_OPTIMIZE, f"benchmarked {len(key_modules)} modules",
                     f"slow imports: {len(slow_imports)}, parse: {parse_time:.3f}s")
        logger.info(f"  ⏱  Parse time: {parse_time:.3f}s | Slow imports: {len(slow_imports)}")

        if slow_imports:
            details = ", ".join(f"{s['module']}({s['time']}s)" for s in slow_imports)
            logger.info(f"  ⚠️  Slow: {details}")

    # ══════════════════════════════════════════════════════════════
    # PHASE 5: RESEARCH — ਨਵੀਆਂ ਤਕਨੀਕਾਂ ਸਿੱਖੋ
    # ══════════════════════════════════════════════════════════════

    async def _phase_research(self):
        """Research improvements via LLM + Internet (arXiv/web) and QUEUE them."""
        logger.info("📚 Phase 5: Research / ਨਵੀਆਂ ਖੋਜਾਂ")
        try:
            from llm_router import LLMRouter
            router = LLMRouter()

            weakest = sorted(self._scores.items(), key=lambda x: x[1])[:3]
            weakest_names = [Path(k).name for k, _ in weakest]

            # ── Step A: Internet research (arXiv + web) ──────────────
            internet_context = ""
            try:
                internet = self.orc.get_agent("internet")
                if internet:
                    logger.info("  🌐 Searching arXiv for latest AI/ML techniques...")
                    arxiv = await internet.execute({
                        "name": "Research latest AI techniques",
                        "data": {"action": "arxiv",
                                 "query": "autonomous AI self-improvement code generation 2025 2026",
                                 "max_results": 3}
                    })
                    papers = arxiv.get("papers", [])
                    if papers:
                        internet_context = "\n".join(
                            f"📄 {p['title']} ({p['date']}): {p['abstract'][:150]}"
                            for p in papers[:3]
                        )
                        logger.info(f"  📄 Found {len(papers)} relevant papers from arXiv")
                        self._record(PHASE_RESEARCH, "arxiv_search",
                                     f"found {len(papers)} papers", success=True)
            except Exception as e:
                logger.debug(f"  Internet research skipped: {e}")

            # ── Step B: LLM-based improvement suggestions ────────────
            research_section = ""
            if internet_context:
                research_section = (
                    f"\nLatest research from arXiv:\n{internet_context}\n"
                    "Consider techniques from these papers if applicable.\n"
                )

            prompt = (
                f"You are improving an autonomous AI platform (AMRIT GODMODE). Cycle {self.cycle}.\n"
                f"Files needing the most improvement: {weakest_names}\n"
                f"Quality trend: {self._quality_trend[-5:]}\n"
                f"{research_section}\n"
                "Give 3 CONCRETE improvements as JSON list:\n"
                '[{"file": "filename.py", "action": "add_docstring|add_type_hints|add_error_handling|'
                'add_logging|add_retry|simplify", "detail": "specific change description"},...]\n'
                "Only suggest safe, backwards-compatible changes. Output ONLY the JSON array."
            )
            raw = await router.complete(prompt, max_tokens=400)

            # Try to extract JSON from response
            pending = []
            try:
                import re
                match = re.search(r'\[.*?\]', raw, re.DOTALL)
                if match:
                    pending = json.loads(match.group())
                    # Validate structure
                    pending = [p for p in pending
                               if isinstance(p, dict) and "file" in p and "action" in p]
            except Exception:
                pass

            if pending:
                # Merge with existing pending improvements (avoid duplicates)
                existing = self._load_pending()
                seen = {(p.get("file"), p.get("action")) for p in existing}
                new_items = [p for p in pending
                             if (p.get("file"), p.get("action")) not in seen]
                existing.extend(new_items)
                self._save_pending(existing)
                self._record(PHASE_RESEARCH, "research_improvements",
                             f"queued {len(new_items)} new improvements", success=True)
                logger.info(f"  📚 Queued {len(new_items)} new improvements for next apply cycle")
            else:
                self._record(PHASE_RESEARCH, "research_improvements",
                             "no structured suggestions", success=True)
                logger.info("  📚 Research done — no structured items to queue")
        except Exception as e:
            self._record(PHASE_RESEARCH, "research", str(e), success=False)

    def _load_pending(self) -> list:
        """Load pending improvements from disk."""
        if PENDING_FILE.exists():
            try:
                return json.loads(PENDING_FILE.read_text())
            except Exception:
                pass
        return []

    def _save_pending(self, items: list):
        """Persist pending improvements to disk."""
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        PENDING_FILE.write_text(json.dumps(items[:50], indent=2))

    async def _apply_pending_improvements(self) -> int:
        """Apply safe pending improvements using targeted function-by-function editing.

        Instead of rewriting the whole file (which fails for large files),
        we extract individual functions via AST, improve each one, and stitch back.
        """
        pending = self._load_pending()
        if not pending:
            return 0

        coder = self.orc.get_agent("coder")
        if not coder:
            return 0

        SAFE_ACTIONS = {"add_docstring", "add_type_hints", "add_logging", "add_error_handling"}
        CAREFUL_ACTIONS = {"add_retry", "simplify"}

        applied = 0
        remaining = []

        for item in pending:
            if applied >= 4:
                remaining.append(item)
                continue

            fname = item.get("file", "")
            action = item.get("action", "")
            detail = item.get("detail", "")
            fp = Path(fname)

            PROTECTED = {"self_evolution.py", "upgrade_agent.py", "orchestrator.py",
                         "base_agent.py", "event_bus.py", "config_loader.py", "main.py"}
            if not fp.exists() or fname in PROTECTED or fname in self._blacklist:
                continue

            if action not in SAFE_ACTIONS and action not in CAREFUL_ACTIONS:
                logger.info(f"  ⏭️  Dropping unsupported action '{action}' for {fname}")
                continue

            code = fp.read_text(errors="ignore")
            self._backup(fp)

            # ── Find functions that need this specific improvement ──
            targets = self._find_functions_needing(code, action)
            if not targets:
                logger.info(f"  ⏭️  {fname}: no functions need '{action}' — dropping")
                continue

            logger.info(f"  🎯 {fname}: {len(targets)} function(s) need '{action}'")

            file_changed = False
            for func_name in targets[:5]:  # Max 5 functions per file per cycle
                func_src = self._extract_function_source(code, func_name)
                if not func_src:
                    continue

                instructions = self._build_improve_instructions(action, detail, func_name)
                last_err = None
                for attempt in range(1, 4):  # 2× 7B + 1× 32B escalation
                    try:
                        if last_err:
                            instructions_with_feedback = (
                                f"PREVIOUS ATTEMPT FAILED: {last_err}\n"
                                "Fix the error and try again.\n\n" + instructions
                            )
                        else:
                            instructions_with_feedback = instructions

                        # Escalate to 32B on final attempt
                        category = "deep" if attempt == 3 else "refactor"
                        if attempt == 3:
                            logger.info("  \U0001f9e0 7B ਫੇਲ੍ਹ — Qwen3-32B ਨਾਲ ਕੋਸ਼ਿਸ਼...")

                        result = await coder.execute({
                            "name": f"Improve {func_name} in {fname}",
                            "data": {
                                "action": "refactor",
                                "code": func_src,
                                "category": category,
                                "error": instructions_with_feedback,
                            }
                        })
                        new_func = result.get("code", "").strip()
                        if not new_func or func_name not in new_func:
                            last_err = f"Response empty or missing {func_name}"
                            continue

                        try:
                            ast.parse(new_func)
                        except SyntaxError as e:
                            last_err = str(e)
                            if attempt < 3:
                                logger.info(f"  ⚠️  {fname}::{func_name}: syntax error, retrying")
                            continue

                        new_code = self._replace_function_in_source(code, func_name, func_src, new_func)
                        if not new_code or new_code == code:
                            last_err = "Stitch produced no changes"
                            continue

                        try:
                            ast.parse(new_code)
                        except SyntaxError as e:
                            last_err = f"Full-file syntax error after stitch: {e}"
                            continue

                        code = new_code  # Update code for next function
                        file_changed = True
                        logger.info(f"  ✅ {fname}::{func_name}() — '{action}' applied")
                        break
                    except Exception as e:
                        last_err = str(e)
                        continue

            if file_changed:
                fp.write_text(code)
                applied += 1
                self._record("apply", f"{action} on {fname}",
                             f"targeted edit on {len(targets)} functions", success=True)
                logger.info(f"  ✅ Applied '{action}' to {fname}")
            else:
                self._restore(fp)
                remaining.append(item)

        self._save_pending(remaining)
        return applied

    def _find_functions_needing(self, code: str, action: str) -> list:
        """Find function names that need a specific improvement, via AST inspection."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        targets = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") and node.name != "__init__":
                continue  # Skip private helpers, focus on public/init
            body = node.body

            if action == "add_error_handling":
                has_try = any(isinstance(s, ast.Try) for s in body)
                if not has_try and len(body) >= 3:
                    targets.append(node.name)

            elif action == "add_logging":
                func_lines = ast.get_source_segment(code, node) or ""
                if "logger." not in func_lines and "logging." not in func_lines and len(body) >= 3:
                    targets.append(node.name)

            elif action == "add_type_hints":
                if node.returns is None and len(body) >= 2:
                    targets.append(node.name)

            elif action == "add_docstring":
                has_doc = (body and isinstance(body[0], ast.Expr)
                           and isinstance(body[0].value, (ast.Constant, ast.Str)))
                if not has_doc and len(body) >= 2:
                    targets.append(node.name)

        return targets

    @staticmethod
    def _build_improve_instructions(action: str, detail: str, func_name: str) -> str:
        """Build LLM instructions for a specific improvement action on a single function."""
        base = {
            "add_error_handling": (
                f"Add try-except error handling to {func_name}(). "
                "Wrap the main logic in a try block. Catch specific exceptions "
                "(not bare except). Log errors with logger.error(). "
                "Re-raise or return a sensible default."
            ),
            "add_logging": (
                f"Add logging to {func_name}(). "
                "Add logger.info() at entry with key params. "
                "Add logger.debug() for important intermediate steps. "
                "Add logger.error() in any except blocks. "
                "Use: from logger import setup_logger; logger = setup_logger(__name__)"
            ),
            "add_type_hints": (
                f"Add type hints to {func_name}(). "
                "Add parameter type annotations and return type. "
                "Use standard typing imports (Optional, List, Dict, etc.)."
            ),
            "add_docstring": (
                f"Add a docstring to {func_name}(). "
                "Use Google-style docstring with Args, Returns, Raises sections."
            ),
        }
        instructions = base.get(action, f"Apply '{action}' to {func_name}(). {detail}")
        return (
            f"{instructions}\n\n"
            "RULES:\n"
            "- Return ONLY the improved function (not the whole file).\n"
            "- Keep the function signature, name, and behavior identical.\n"
            "- Do NOT change any existing logic.\n"
            "- Return valid Python in a ```python block."
        )

    # ══════════════════════════════════════════════════════════════
    # PHASE 6: LEARN — ਸਬਕ ਸਿੱਖੋ
    # ══════════════════════════════════════════════════════════════

    async def _phase_learn(self):
        """Record lessons AND actually apply pending improvements."""
        logger.info("🧠 Phase 6: Learn + Apply / ਸਬਕ ਸਿੱਖੋ ਤੇ ਲਾਗੂ ਕਰੋ")

        # Track quality trend
        avg_q = sum(self._scores.values()) / max(len(self._scores), 1)
        self._quality_trend.append(round(avg_q, 3))
        if len(self._quality_trend) > 20:
            self._quality_trend = self._quality_trend[-20:]

        # APPLY pending improvements (1-2 per cycle, safe actions only)
        pre_apply_test = await self._phase_test() if self._load_pending() else None
        applied_count = await self._apply_pending_improvements()
        if applied_count:
            logger.info(f"  🔨 Applied {applied_count} pending improvement(s) from research queue")
            # ── TEST AFTER APPLY — ਟੈਸਟ ਕਰੋ ਅਪਲਾਈ ਤੋਂ ਬਾਅਦ ──
            post_apply_test = await self._phase_test()
            if pre_apply_test:
                self._verify_fix_impact(pre_apply_test, post_apply_test)

        cycle_entries = [e for e in self._log if e.get("cycle") == self.cycle]
        successes = sum(1 for e in cycle_entries if e.get("success"))
        failures = sum(1 for e in cycle_entries if not e.get("success"))

        # Quality trend summary
        if len(self._quality_trend) >= 3:
            trend = self._quality_trend[-1] - self._quality_trend[-3]
            if trend > 0.005:
                logger.info(f"  📈 Quality trending UP: {self._quality_trend[-3]:.3f} → {self._quality_trend[-1]:.3f}")
            elif trend < -0.005:
                logger.warning(f"  📉 Quality trending DOWN: {self._quality_trend[-3]:.3f} → {self._quality_trend[-1]:.3f}")
            else:
                logger.info(f"  ➡️  Quality stable at {self._quality_trend[-1]:.3f}")

        # Extract ACTIONABLE lesson from this cycle
        lesson = {
            "cycle": self.cycle,
            "successes": successes,
            "failures": failures,
            "avg_quality": round(avg_q, 3),
            "quality_trend": self._quality_trend[-5:],
            "weakest_files": sorted(self._scores.items(), key=lambda x: x[1])[:3],
            "what_worked": [],
            "what_failed": [],
        }

        for entry in cycle_entries:
            if entry.get("success"):
                lesson["what_worked"].append(entry.get("action", "")[:100])
            else:
                lesson["what_failed"].append(entry.get("action", "")[:100])

        self._lessons.append(lesson)
        self._save_lessons()

        self._record(PHASE_LEARN, f"cycle {self.cycle} done",
                     f"{successes}✅ {failures}❌ | quality={avg_q:.3f} | "
                     f"pending={len(self._load_pending())} improvements")

        # Record failures to failure pattern DB (never lose them)
        try:
            from memory_agent import FailurePatternDB
            fdb = FailurePatternDB()
            for entry in cycle_entries:
                if not entry.get("success"):
                    fdb.record_failure(
                        error=entry.get("result", "")[:300],
                        agent="self_evolution",
                        task=entry.get("action", ""),
                    )
        except Exception:
            pass

        # ── LearningLayer — ਸਿੱਖਣ ਦੀ ਪਰਤ ──
        try:
            from learning_layer import LearningLayer
            ll = LearningLayer()
            # ਹਰ ਫੇਲ੍ਹ ਘਟਨਾ ਨੂੰ observe ਕਰੋ
            for entry in cycle_entries:
                if not entry.get("success"):
                    ll.observe({
                        "agent": "self_evolution",
                        "action": entry.get("action", ""),
                        "success": False,
                        "error": entry.get("result", "")[:200],
                    })
            # ਸੋਚੋ — ਕੀ ਪੈਟਰਨ ਮਿਲੇ?
            insights = ll.reflect()
            if insights:
                for ins in insights[:2]:
                    ll.record_lesson(ins.get("advice", ""), source="selffix", tags=["auto"])
            # ਸਬਕ ਸੇਵ ਕਰੋ
            ll.record_lesson(
                f"Cycle {self.cycle}: {successes}✅ {failures}❌ | quality={avg_q:.3f}",
                source="selffix_cycle",
                tags=["cycle_summary"]
            )
            stats = ll.stats()
            logger.info(f"  🌸 LearningLayer: {stats['total_lessons']} ਸਬਕ, "
                        f"{stats['patterns_with_fix']}/{stats['total_error_patterns']} ਹੱਲ ਹੋਏ")
        except Exception as e:
            logger.debug(f"  LearningLayer: {e}")

        # Update experience log
        try:
            from experience_log import ExperienceLog
            xp = ExperienceLog()
            xp.record(
                agent="self_evolution",
                action=f"evolution_cycle_{self.cycle}",
                task=f"cycle {self.cycle}: {successes} successes, {failures} failures",
                result={"cycle": self.cycle, "successes": successes, "failures": failures,
                        "scores": dict(sorted(self._scores.items(), key=lambda x: x[1])[:5])},
                success=failures == 0
            )
            xp.save()
        except Exception:
            pass

        self._record(PHASE_LEARN, f"cycle {self.cycle} done",
                     f"{successes}✅ {failures}❌ | {len(self._lessons)} lessons total")
        self._save_log()

    def _verify_fix_impact(self, before: dict, after: dict):
        """Compare before/after test results — did our fixes actually help?"""
        before_pass = before.get("passed", 0)
        after_pass  = after.get("passed", 0)
        before_fail = before.get("failed", 0)
        after_fail  = after.get("failed", 0)
        before_imports = len(before.get("import_errors", []))
        after_imports  = len(after.get("import_errors", []))

        improved = after_pass > before_pass or after_fail < before_fail
        regressed = after_fail > before_fail or after_imports > before_imports

        if improved:
            logger.info(f"  📈 IMPROVED: {before_pass}→{after_pass} passed, "
                        f"{before_fail}→{after_fail} failed")
            self._record("verify", "fix_impact", "improved", success=True)
        elif regressed:
            logger.warning(f"  📉 REGRESSION: {before_pass}→{after_pass} passed, "
                           f"{before_fail}→{after_fail} failed. Consider reverting.")
            self._record("verify", "fix_impact", "regressed", success=False)
            # Blacklist files that were just fixed (they caused regression)
            recent_cycle_fixes = [fname for fname, cycles in self._fix_history.items()
                                  if self.cycle in cycles]
            for fname in recent_cycle_fixes:
                regression_count = sum(
                    1 for e in self._log
                    if e.get("phase") == "verify" and not e.get("success")
                )
                if regression_count >= 2:
                    self._blacklist.add(fname)
                    logger.warning(f"  ⛔ BLACKLISTED: {fname} — caused 2+ regressions")
            # Record regression as a failure pattern
            try:
                from memory_agent import FailurePatternDB
                fdb = FailurePatternDB()
                fdb.record_failure(
                    error=f"Fix regression: before={before_pass}ok/{before_fail}fail, "
                          f"after={after_pass}ok/{after_fail}fail",
                    agent="self_evolution",
                    task=f"cycle_{self.cycle}_fix",
                )
            except Exception:
                pass
        else:
            logger.info(f"  ➖ No change: {after_pass} passed, {after_fail} failed")
            self._record("verify", "fix_impact", "no_change")

    # ══════════════════════════════════════════════════════════════
    # EXECUTE USER TASK — ਯੂਜ਼ਰ ਦਾ ਕੰਮ ਕਰੋ
    # ══════════════════════════════════════════════════════════════

    async def _execute_user_task(self, goal: str):
        """Execute a user task through the normal pipeline, then learn from it."""
        logger.info(f"\n{'═' * 50}")
        logger.info(f"  📋 USER TASK: {goal}")
        logger.info(f"{'═' * 50}")

        t0 = time.time()
        try:
            await self.orc.run_goal(goal)
            elapsed = time.time() - t0
            self._record("user_task", goal, f"completed in {elapsed:.1f}s")
            logger.info(f"  ✅ Task completed in {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            self._record("user_task", goal, str(e), success=False)
            logger.error(f"  ❌ Task failed after {elapsed:.1f}s: {e}")

    # ══════════════════════════════════════════════════════════════
    # UTILITIES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ══════════════════════════════════════════════════════════════

    def _backup(self, filepath: Path):
        """Create backup before modifying any file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = BACKUP_DIR / f"{filepath.name}.{ts}.bak"
        try:
            shutil.copy2(filepath, backup)
        except Exception:
            pass

    def _restore(self, filepath: Path):
        """Restore most recent backup if fix failed."""
        backups = sorted(BACKUP_DIR.glob(f"{filepath.name}.*.bak"), reverse=True)
        if backups:
            try:
                shutil.copy2(backups[0], filepath)
                logger.info(f"  ↩️  Restored {filepath.name} from backup")
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════
    # PHASE 7: PUNJABI MODEL TRAINING — ਪੰਜਾਬੀ LoRA ਟ੍ਰੇਨਿੰਗ
    # ══════════════════════════════════════════════════════════════

    async def _phase_train_punjabi(self):
        """Run one LoRA training cycle on Punjabi datasets using MLX."""
        logger.info("🎓 Phase 7: Punjabi Model Training / ਪੰਜਾਬੀ ਮਾਡਲ ਸਿਖਲਾਈ")
        try:
            from punjabi_trainer import PunjabiTrainer
            trainer = PunjabiTrainer()

            # Check if model already plateaued (no improvement in 3+ cycles)
            if trainer.is_best():
                logger.info("  ✅ Model already at best — skipping training")
                self._record("train_punjabi", "skip", "model at best", success=True)
                return

            result = await trainer.run_cycle()
            status = result.get("status", "error")

            if status == "improved":
                logger.info(f"  📈 Model improved: {result.get('prev_loss', '?'):.4f} → {result.get('new_loss', '?'):.4f}")
                if result.get("deployed"):
                    logger.info("  🚀 Deployed as amrit-coder-v2 in Ollama")
                self._record("train_punjabi", "improved", str(result), success=True)
            elif status == "no_improvement":
                logger.info(f"  ➡️  No improvement this cycle (loss: {result.get('current_loss', '?'):.4f})")
                self._record("train_punjabi", "plateau", str(result), success=True)
            else:
                logger.warning(f"  ⚠️  Training issue: {result.get('error', 'unknown')[:100]}")
                self._record("train_punjabi", "error", str(result.get("error", "")), success=False)

        except ImportError:
            logger.info("  ⏭  MLX not installed — skipping Punjabi training")
        except Exception as e:
            logger.error(f"  ❌ Punjabi training error: {e}")
            self._record("train_punjabi", "error", str(e), success=False)

    def _print_cycle_summary(self):
        """Print a nice summary of this cycle + structured JSON report."""
        cycle_entries = [e for e in self._log if e.get("cycle") == self.cycle]
        successes = sum(1 for e in cycle_entries if e.get("success"))
        failures  = sum(1 for e in cycle_entries if not e.get("success"))
        total_files = len(self._scores)
        avg_score = sum(self._scores.values()) / max(total_files, 1)

        fixed_this_cycle    = [fname for fname, cycles in self._fix_history.items()
                                if self.cycle in cycles]
        refactored_this_cycle = [fname for fname, cycles in self._refactor_history.items()
                                 if self.cycle in cycles]
        applied_this_cycle   = [e.get("action", "").replace("apply ", "") for e in cycle_entries
                                if e.get("phase") == "apply" and e.get("success")]
        regressed_files      = [e.get("action", "") for e in cycle_entries
                                if not e.get("success") and "regress" in e.get("result", "").lower()]
        human_review         = [e.get("action", "").replace("escalate ", "") for e in cycle_entries
                                if "escalate" in e.get("action", "")]
        pending_count        = len(self._load_pending())
        plateau              = (not fixed_this_cycle and not refactored_this_cycle
                                and not applied_this_cycle and failures == 0)
        root_cause           = next(
            (e.get("result", "") for e in cycle_entries if e.get("action") == "root_cause"), "")

        # Quality trend arrow
        if len(self._quality_trend) >= 2:
            delta = self._quality_trend[-1] - self._quality_trend[-2]
            trend_arrow = "📈" if delta > 0.002 else ("📉" if delta < -0.002 else "➡️")
        else:
            trend_arrow = "➡️"

        report = {
            "cycle": self.cycle,
            "files_fixed": fixed_this_cycle,
            "files_refactored": refactored_this_cycle,
            "improvements_applied": applied_this_cycle,
            "files_regressed": regressed_files,
            "blacklisted_files": list(self._blacklist),
            "quality_trend": self._quality_trend[-5:],
            "pending_improvements": pending_count,
            "write_verified": not any("write_failed" in e.get("action", "") for e in cycle_entries),
            "root_cause_hypothesis": root_cause,
            "plateau_detected": plateau,
            "human_review_needed": human_review,
        }

        print(f"\n  {'─' * 50}")
        print(f"  │ 🔄 CYCLE {self.cycle} SUMMARY / ਚੱਕਰ ਸੰਖੇਪ")
        print(f"  │ ✅ Successes: {successes}  ❌ Failures: {failures}")
        print(f"  │ 📊 Files: {total_files}  Quality: {avg_score:.3f} {trend_arrow}")
        if fixed_this_cycle:
            print(f"  │ 🔧 Fixed: {', '.join(fixed_this_cycle)}")
        if refactored_this_cycle:
            print(f"  │ ✂️  Refactored: {', '.join(refactored_this_cycle)}")
        if applied_this_cycle:
            print(f"  │ 🔨 Applied: {', '.join(applied_this_cycle)}")
        if pending_count:
            print(f"  │ 📋 Pending improvements: {pending_count}")
        if self._blacklist:
            print(f"  │ ⛔ Blacklisted: {', '.join(self._blacklist)}")
        if human_review:
            print(f"  │ 🚨 Human Review: {', '.join(human_review)}")
        if plateau:
            print("  │ 🛑 PLATEAU — no improvements this cycle")
        if self._benchmarks.get("goal_parse_rules"):
            print(f"  │ ⏱  Parse Speed: {self._benchmarks['goal_parse_rules']:.3f}s")
        print(f"  {'─' * 50}")
        print(f"  EVOLUTION REPORT: {json.dumps(report, ensure_ascii=False)}")
        print(f"  {'─' * 50}\n")

    # ══════════════════════════════════════════════════════════════
    # QUICK MODES — ਇੱਕ ਵਾਰ ਦੀ ਜਾਂਚ
    # ══════════════════════════════════════════════════════════════

    async def run_single_analysis(self) -> dict:
        """Run just one analysis + test cycle. Returns a report."""
        self.cycle += 1
        issues = await self._phase_analyze()
        test_results = await self._phase_test()

        return {
            "cycle": self.cycle,
            "total_files": len(self._scores),
            "avg_quality": round(sum(self._scores.values()) / max(len(self._scores), 1), 2),
            "files_with_issues": len(issues),
            "test_passed": test_results["passed"],
            "test_failed": test_results["failed"],
            "import_errors": len(test_results.get("import_errors", [])),
            "weakest_files": sorted(self._scores.items(), key=lambda x: x[1])[:5],
            "issues": issues[:5],
            "import_error_details": test_results.get("import_errors", [])[:5],
        }

    async def run_fix_cycle(self) -> dict:
        """Run one full fix cycle: analyze → test → fix → test again."""
        self.cycle += 1
        logger.info("🔧 Single fix cycle starting...")

        issues = await self._phase_analyze()
        test_before = await self._phase_test()

        FIXABLE_TYPES = {"syntax_error", "empty_file", "todo", "not_implemented", "bare_except", "lint_errors"}
        ADVISORY_TYPES = {"long_function"}
        critical_issues = [i for i in issues
                           if any(x["type"] in FIXABLE_TYPES for x in i["issues"])]
        advisory_issues = [i for i in issues
                           if any(x["type"] in ADVISORY_TYPES for x in i["issues"])]

        if critical_issues or test_before.get("failures") or test_before.get("import_errors"):
            await self._phase_fix(critical_issues, test_before)
            test_after = await self._phase_test()
        else:
            test_after = test_before

        # Refactor long functions (the main cause of weak file scores)
        if advisory_issues:
            await self._phase_refactor(advisory_issues)
            test_after = await self._phase_test()
        elif not critical_issues:
            logger.info("  ✨ No issues found — system is clean!")

        await self._phase_learn()
        self._save_log()

        return {
            "cycle": self.cycle,
            "before": {"passed": test_before["passed"], "failed": test_before["failed"]},
            "after": {"passed": test_after["passed"], "failed": test_after["failed"]},
            "improved": test_after["passed"] > test_before["passed"] or
                        test_after["failed"] < test_before["failed"]
        }
