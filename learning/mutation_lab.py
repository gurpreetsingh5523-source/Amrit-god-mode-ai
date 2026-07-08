#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║  🧪 mutation_lab.py — ਵਿਕਾਸਵਾਦੀ ਪ੍ਰੋਗ੍ਰਾਮਿੰਗ           ║
║                                                      ║
║  Flow:                                               ║
║    generate variant → sandbox test →                ║
║    benchmark → compare → accept/reject               ║
║                                                      ║
║  This is evolutionary programming.                   ║
║  Safe, sandboxed, measurable.                        ║
╚══════════════════════════════════════════════════════╝
"""

import sqlite3, json, time, hashlib, subprocess, tempfile, os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from config import CFG
from llm_client import LLMClient


class MutationLab:
    """
    Self-modification ਸਾਫ਼ ਤਰੀਕੇ ਨਾਲ:
    sandbox + versioning + rollback + scoring
    """

    def __init__(self):
        self.db = CFG.memory_dir / "mutations.db"
        self.sandbox_dir = CFG.sandbox_dir
        self.vault_dir = CFG.vault_dir
        self.llm = LLMClient(system_prompt=
            "You are a code mutation engine. Generate SMALL, FOCUSED code variants. "
            "Each variant should be a specific improvement or experiment. "
            "Code must be valid Python.")
        self._init_db()
        print(f"🧪 MutationLab — {self._count()} variants in vault")

    def _init_db(self):
        with sqlite3.connect(self.db) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS mutations (
                id TEXT PRIMARY KEY,
                parent_code TEXT,
                mutation_type TEXT,  -- "enhance"|"optimize"|"experiment"
                variant_code TEXT NOT NULL,
                description TEXT,
                created TEXT
            );

            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mutation_id TEXT,
                test_type TEXT,      -- "syntax"|"runtime"|"benchmark"
                passed INTEGER,      -- 0 or 1
                score REAL,           -- benchmark score
                error TEXT,
                timestamp TEXT,
                FOREIGN KEY (mutation_id) REFERENCES mutations(id)
            );

            CREATE TABLE IF NOT EXISTS accepted_variants (
                id TEXT PRIMARY KEY,
                mutation_id TEXT,
                variant_code TEXT,
                improvement_percent REAL,
                accepted_at TEXT,
                FOREIGN KEY (mutation_id) REFERENCES mutations(id)
            );
            """)

    def _count(self) -> int:
        with sqlite3.connect(self.db) as c:
            return c.execute(
                "SELECT COUNT(*) FROM accepted_variants"
            ).fetchone()[0]

    # ─────────────────────────────────────────────
    # GENERATE VARIANTS
    # ─────────────────────────────────────────────

    def generate(self, target_code: str,
                 goal: str = "improve performance",
                 mutation_type: str = "enhance") -> str:
        """
        ਮੌਜੂਦਾ code ਦਾ variant ਬਣਾਓ

        mutation_type:
          "enhance" - ਨਈਆਂ ਸਮਰੱਥਾਵਾਂ
          "optimize" - ਤੇਜ਼ੀ/ਸਥਿਰਤਾ
          "experiment" - ਨਵਾਂ approach
        """
        print(f"\n🧪 Generating {mutation_type} variant...")

        prompt = f"""Code Mutation Task:

ORIGINAL CODE:
```python
{target_code[:1000]}
```

GOAL: {goal}
MUTATION TYPE: {mutation_type}

Generate ONE improved variant of this code.
Focus on:
- {mutation_type == 'enhance' and 'Adding new useful features' or
  mutation_type == 'optimize' and 'Making it faster, cleaner' or
  'Trying a completely different approach'}

Requirements:
1. Valid Python syntax
2. Keep the same function signature if applicable
3. Add comments explaining changes
4. Max 100 lines
5. NO external dependencies not already used

Output ONLY the improved code block."""

        variant = self.llm.ask(prompt)
        mut_id = hashlib.sha256(
            f"{target_code}{variant}{time.time()}".encode()
        ).hexdigest()[:12]

        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO mutations
                (id, parent_code, mutation_type, variant_code, description, created)
                VALUES (?,?,?,?,?,?)
            """, (mut_id, target_code[:500], mutation_type,
                  variant, goal, datetime.now().isoformat()))

        print(f"  ✓ Variant: {mut_id}")
        return mut_id

    # ─────────────────────────────────────────────
    # SANDBOX TESTING
    # ─────────────────────────────────────────────

    def test_syntax(self, mutation_id: str) -> Tuple[bool, str]:
        """ਸਿੰਟੈਕਸ ਚੈਕ ਕਰੋ"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT variant_code FROM mutations WHERE id=?",
                (mutation_id,)
            ).fetchone()

        if not row:
            return False, "Mutation not found"

        code = row[0]
        try:
            compile(code, '<variant>', 'exec')
            self._log_test(mutation_id, "syntax", True, 1.0)
            return True, "✓ Syntax OK"
        except SyntaxError as e:
            self._log_test(mutation_id, "syntax", False, 0.0, str(e))
            return False, f"Syntax error: {e}"

    def test_runtime(self, mutation_id: str,
                     test_input: str = "x = 1") -> Tuple[bool, str]:
        """ਸਾਧਾਰਣ runtime test"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT variant_code FROM mutations WHERE id=?",
                (mutation_id,)
            ).fetchone()

        if not row:
            return False, "Mutation not found"

        code = row[0]

        # Temp file ਵਿੱਚ ਲਿਖੋ
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                         dir=self.sandbox_dir,
                                         delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['python3', temp_path],
                capture_output=True, timeout=CFG.sandbox_timeout,
                text=True
            )
            success = result.returncode == 0
            error = result.stderr if result.stderr else result.stdout[:100]
            self._log_test(mutation_id, "runtime", success, 1.0 if success else 0.0, error)
            return success, error if error else "✓ Runtime OK"
        except subprocess.TimeoutExpired:
            self._log_test(mutation_id, "runtime", False, 0.0, "Timeout")
            return False, "Timeout"
        except Exception as e:
            self._log_test(mutation_id, "runtime", False, 0.0, str(e))
            return False, str(e)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # ─────────────────────────────────────────────
    # DUALBRAIN SANDBOX — ਪੂਰਾ stdout ਵਾਪਸ (truncate ਨਹੀਂ)
    # ─────────────────────────────────────────────
    def run_in_sandbox(self, code: str, timeout: int = None) -> Tuple[bool, str]:
        """
        DualBrainEngine v3 ਲਈ: ਦਿੱਤੇ code (test driver) ਨੂੰ ਵੱਖਰੇ python
        process ਵਿੱਚ ਚਲਾਓ ਅਤੇ ਪੂਰਾ stdout ਵਾਪਸ ਕਰੋ — ਤਾਂ ਜੋ
        __EVAL_JSON__ marker ਕੱਟਿਆ ਨਾ ਜਾਵੇ।

        (ਪੁਰਾਣਾ test_runtime() stdout ਨੂੰ 100 chars 'ਤੇ ਕੱਟ ਦਿੰਦਾ ਸੀ —
         ਇਹ method ਉਹ ਮਸਲਾ ਠੀਕ ਕਰਦਾ ਹੈ।)

        Returns: (ran_ok, full_stdout)
        """
        timeout = timeout or getattr(CFG, "sandbox_timeout", 10)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                         dir=self.sandbox_dir,
                                         delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_path = f.name
        try:
            result = subprocess.run(
                ["python3", temp_path],
                capture_output=True, text=True, timeout=timeout)
            ran = (result.returncode == 0)
            out = (result.stdout or "")
            if result.stderr:
                out += "\nSTDERR:\n" + result.stderr
            return ran, out
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        except Exception as e:
            return False, f"sandbox error: {e}"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def benchmark(self, mutation_id: str,
                  benchmark_code: str = "") -> float:
        """ਪ੍ਰਦਰਸ਼ਨ ਮਾਪੋ (0-1 scale)"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT variant_code FROM mutations WHERE id=?",
                (mutation_id,)
            ).fetchone()

        if not row:
            return 0.0

        # Simple metric: lines of code + comments = bad, concise = good
        code = row[0]
        lines = len(code.split('\n'))
        comments = code.count('#')
        complexity = lines - comments  # Fewer lines = better

        score = max(0, 1.0 - (complexity / 50.0))  # Normalize
        self._log_test(mutation_id, "benchmark", True, score)
        return score

    def _log_test(self, mutation_id: str, test_type: str,
                  passed: bool, score: float = 0.0, error: str = ""):
        with sqlite3.connect(self.db) as c:
            c.execute("""
                INSERT INTO test_results
                (mutation_id, test_type, passed, score, error, timestamp)
                VALUES (?,?,?,?,?,?)
            """, (mutation_id, test_type, int(passed), score,
                  error[:200], datetime.now().isoformat()))

    # ─────────────────────────────────────────────
    # ACCEPTANCE LOGIC
    # ─────────────────────────────────────────────

    def evaluate(self, mutation_id: str) -> Tuple[bool, Dict]:
        """
        ਪূरੀ ਤਰ੍ਹਾਂ test ਕਰੋ ਅਤੇ ਫ਼ੈਸਲਾ ਲਵੋ

        Returns: (accept, results_dict)
        """
        print(f"\n🧪 Evaluating {mutation_id}...")

        # 1. Syntax
        syntax_ok, _ = self.test_syntax(mutation_id)
        if not syntax_ok:
            return False, {"passed": False, "reason": "Syntax error"}

        # 2. Runtime
        runtime_ok, _ = self.test_runtime(mutation_id)
        if not runtime_ok:
            return False, {"passed": False, "reason": "Runtime error"}

        # 3. Benchmark
        score = self.benchmark(mutation_id)

        results = {
            "passed": True,
            "syntax_ok": syntax_ok,
            "runtime_ok": runtime_ok,
            "benchmark_score": round(score, 3),
            "accept_threshold": 0.6,
            "accepted": score >= 0.6
        }

        if results["accepted"]:
            self._accept(mutation_id, score)
            print(f"  ✅ ACCEPTED! Score: {score:.3f}")
        else:
            print(f"  ❌ REJECTED. Score: {score:.3f} < {0.6}")

        return results["accepted"], results

    def _accept(self, mutation_id: str, improvement: float):
        """Variant ਸਵੀਕਾਰ ਕਰੋ"""
        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT variant_code FROM mutations WHERE id=?",
                (mutation_id,)
            ).fetchone()
            if row:
                c.execute("""
                    INSERT INTO accepted_variants
                    (id, mutation_id, variant_code, improvement_percent, accepted_at)
                    VALUES (?,?,?,?,?)
                """, (f"acc_{mutation_id}", mutation_id, row[0],
                      improvement * 100, datetime.now().isoformat()))

                # Vault ਵਿੱਚ ਸੇਵ ਕਰੋ
                vault_file = self.vault_dir / f"variant_{mutation_id}.py"
                vault_file.write_text(row[0])

    def get_best_variants(self, limit: int = 5) -> List[Dict]:
        """ਸਭ ਤੋਂ ਵਧੀਆ accepted variants"""
        with sqlite3.connect(self.db) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("""
                SELECT * FROM accepted_variants
                ORDER BY improvement_percent DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def status(self) -> Dict:
        with sqlite3.connect(self.db) as c:
            total    = c.execute("SELECT COUNT(*) FROM mutations").fetchone()[0]
            accepted = c.execute("SELECT COUNT(*) FROM accepted_variants").fetchone()[0]
            tests    = c.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        return {
            "total_mutations": total,
            "accepted": accepted,
            "tests_run": tests,
            "acceptance_rate": round(accepted / max(1, total), 3)
        }


# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    lab = MutationLab()

    # Original code
    original = """def search_web(query):
    results = []
    for item in query.split():
        results.append(item.upper())
    return results"""

    # Generate variant
    mut_id = lab.generate(original, goal="make it faster",
                          mutation_type="optimize")

    # Test
    ok, info = lab.evaluate(mut_id)
    print(f"\nResult: {info}")

    lab_status = lab.status()
    print(f"\n📊 Lab status: {lab_status}")
