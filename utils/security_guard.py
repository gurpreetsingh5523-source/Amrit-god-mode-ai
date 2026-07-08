#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_guard.py — Static AST Security Scan

DeepMind "From AGI to ASI" (5.5, frictions) ਦੀ ਸਿੱਖਿਆ:
  Recursive self-improvement ਵਿੱਚ ਸਭ ਤੋਂ ਵੱਡਾ friction "safety/control" ਹੈ।
  ਜੇ ਸਿਸਟਮ ਖ਼ੁਦ ਕੋਡ ਲਿਖ ਕੇ ਚਲਾ ਰਿਹਾ ਹੈ, ਤਾਂ ਖ਼ਤਰਨਾਕ ਕੋਡ ਨੂੰ
  sandbox ਤੱਕ ਪਹੁੰਚਣ ਤੋਂ ਪਹਿਲਾਂ ਹੀ ਰੋਕਣਾ ਜ਼ਰੂਰੀ ਹੈ।

ਇਹ ਸਬ-ਸਟਰਿੰਗ matching ਨਾਲੋਂ ਕਿਤੇ ਮਜ਼ਬੂਤ ਹੈ ਕਿਉਂਕਿ ਇਹ ਅਸਲ
Python AST (Abstract Syntax Tree) ਪੜ੍ਹਦਾ ਹੈ — ਕਮੈਂਟ ਜਾਂ ਸਟਰਿੰਗ
ਵਿੱਚ ਲਿਖੇ "subprocess" 'ਤੇ ਗ਼ਲਤ alarm ਨਹੀਂ ਦਿੰਦਾ।
"""

import ast
from typing import List, Tuple


class SecurityGuard:
    """
    Generated code ਨੂੰ sandbox ਤੋਂ ਪਹਿਲਾਂ static scan ਕਰਦਾ ਹੈ।

    ਵਰਤੋਂ:
        guard = SecurityGuard()
        ok, findings = guard.scan(code)
        if not ok:
            print("BLOCKED:", findings)
    """

    # ── ਖ਼ਤਰਨਾਕ modules (import ਕਰਨ 'ਤੇ block) ──
    DENY_MODULES = {
        "subprocess", "socket", "ctypes", "pty", "marshal",
        "multiprocessing", "telnetlib", "ftplib",
    }

    # ── ਖ਼ਤਰਨਾਕ builtin calls ──
    DENY_BUILTINS = {"eval", "exec", "compile", "__import__", "input"}

    # ── ਖ਼ਤਰਨਾਕ attribute calls (module.func) ──
    DENY_ATTR = {
        ("os", "system"), ("os", "popen"), ("os", "remove"),
        ("os", "unlink"), ("os", "rmdir"), ("os", "removedirs"),
        ("os", "kill"), ("os", "fork"),
        ("shutil", "rmtree"), ("shutil", "move"),
    }

    def __init__(self, extra_modules=None, extra_builtins=None):
        """ਵਾਧੂ deny rules ਜੋੜਨ ਲਈ optional parameters"""
        self.deny_modules = set(self.DENY_MODULES)
        self.deny_builtins = set(self.DENY_BUILTINS)
        if extra_modules:
            self.deny_modules |= set(extra_modules)
        if extra_builtins:
            self.deny_builtins |= set(extra_builtins)

    def scan(self, code: str) -> Tuple[bool, List[str]]:
        """
        ਕੋਡ ਨੂੰ scan ਕਰੋ।

        Returns:
            (is_safe, findings)
            is_safe  : True ਜੇ ਕੋਈ ਖ਼ਤਰਾ ਨਹੀਂ
            findings : ਮਿਲੇ ਖ਼ਤਰਿਆਂ ਦੀ ਸੂਚੀ (ਖ਼ਾਲੀ ਜੇ safe)
        """
        findings: List[str] = []

        # ── ਪਹਿਲਾਂ: ਕੀ ਕੋਡ parse ਵੀ ਹੁੰਦਾ ਹੈ? ──
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"SyntaxError: parse ਨਹੀਂ ਹੋਇਆ — {e.msg} (line {e.lineno})"]

        # ── AST walk: ਹਰ node ਜਾਂਚੋ ──
        for node in ast.walk(tree):

            # import subprocess / import socket ...
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self.deny_modules:
                        findings.append(f"denied import: '{alias.name}'")

            # from subprocess import ...
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in self.deny_modules:
                    findings.append(f"denied from-import: '{node.module}'")

            # eval(...) / exec(...) / os.system(...) ...
            elif isinstance(node, ast.Call):
                func = node.func

                # ਸਿੱਧੀ builtin call: eval(), exec()
                if isinstance(func, ast.Name) and func.id in self.deny_builtins:
                    findings.append(f"denied builtin call: '{func.id}()'")

                # attribute call: os.system(), shutil.rmtree()
                elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    pair = (func.value.id, func.attr)
                    if pair in self.DENY_ATTR:
                        findings.append(f"denied call: '{func.value.id}.{func.attr}()'")

        # ── defense-in-depth: high-signal substring fallback ──
        # (AST ਮੁੱਖ ਹੈ; ਇਹ ਸਿਰਫ਼ ਬਹੁਤ ਸਪੱਸ਼ਟ obfuscation ਫੜਨ ਲਈ)
        lowered = code.replace(" ", "")
        for pat in ("os.system(", "subprocess.", "__import__("):
            if pat in lowered and not any(pat[:6] in f for f in findings):
                findings.append(f"suspicious pattern: '{pat}'")

        # ਡੁਪਲੀਕੇਟ ਹਟਾਓ
        findings = sorted(set(findings))
        return (len(findings) == 0), findings


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    guard = SecurityGuard()

    tests = {
        "safe factorial": "def f(n):\n    return 1 if n<2 else n*f(n-1)",
        "os.system":      "import os\nos.system('ls -la')",
        "eval":           "x = eval('2+2')",
        "subprocess":     "import subprocess\nsubprocess.run(['rm','-rf','/'])",
        "string mention": "msg = 'we do not use subprocess here'  # safe comment",
    }

    print("═" * 55)
    print("🛡️  SecurityGuard — Self Test")
    print("═" * 55)
    for name, code in tests.items():
        ok, found = guard.scan(code)
        icon = "✅ SAFE  " if ok else "🚫 BLOCKED"
        print(f"{icon} | {name}")
        for f in found:
            print(f"           → {f}")
