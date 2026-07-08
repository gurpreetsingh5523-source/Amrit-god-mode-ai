"""
safety_layer.py — Amrit God Mode Safety Gatekeeper
═══════════════════════════════════════════════════════════════════
Har destructive kaam (delete, email send, git push, rm, app quit)
ehnu cross karna painda hai. Maqsad: ek galti naal nuksaan na hove.

Layers:
  1. classify(action)        → SAFE | CONFIRM | BLOCK
  2. Trash-not-delete        → files ~/.Trash vich jaande, undo ho sakda
  3. Dry-run                 → pehlan dasse ki karega
  4. Allowlist / Blocklist   → sirf manjoor folders te kaam
  5. Confirmation callback   → voice/text "haan karaan?" puchhe
  6. Audit log               → har action record hunda

Usage:
    from safety_layer import SafetyLayer
    safety = SafetyLayer(confirm_fn=my_voice_confirm)
    if safety.allow("delete", "/path/file"):
        safety.safe_delete("/path/file")     # -> Trash
"""

import re
import json
import subprocess
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Callable, Optional
from logger import setup_logger

logger = setup_logger("SafetyLayer")

AUDIT_LOG = Path("workspace/safety_audit.json")
HOME = Path.home()


class Risk(Enum):
    SAFE    = "safe"      # read, list, search, build code — just do it
    CONFIRM = "confirm"   # delete, send, push, overwrite — ask first
    BLOCK   = "block"     # rm -rf /, format, sudo, system files — never


# ── Patterns ──────────────────────────────────────────────────────

# Commands that must NEVER run, even with confirmation.
HARD_BLOCK = [
    r"rm\s+-rf\s+/(?:\s|$)",          # rm -rf /
    r"rm\s+-rf\s+~(?:/\s*)?$",         # rm -rf ~
    r":\(\)\s*\{.*\|.*&.*\}",          # fork bomb
    r"mkfs",                            # format filesystem
    r"dd\s+if=.*of=/dev/",             # overwrite disk
    r">\s*/dev/sd",                     # write to raw disk
    r"sudo\s+rm",                       # sudo delete
    r"chmod\s+-R\s+777\s+/",           # open root perms
    r"\bshutdown\b", r"\breboot\b",
    r"diskutil\s+erase",
]

# Destructive verbs needing confirmation.
CONFIRM_KEYWORDS = {
    "delete", "remove", "rm ", "trash", "erase", "drop",
    "send", "email", "reply", "post", "publish", "tweet",
    "push", "force", "overwrite", "format", "uninstall",
    "kill", "quit", "shutdown", "wipe", "clear all", "reset",
}

# Folders Amrit may freely operate in (write/delete via Trash).
DEFAULT_ALLOWLIST = [
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Downloads",
    HOME / "Amrit-god-mode-ai" / "workspace",
    Path("/tmp"),
]

# Folders that are ALWAYS off-limits.
PROTECTED = [
    Path("/System"), Path("/Library"), Path("/usr"), Path("/bin"),
    Path("/sbin"), Path("/etc"), Path("/var"), Path("/private/etc"),
    HOME / "Library",
]


class SafetyLayer:
    def __init__(self,
                 confirm_fn: Optional[Callable[[str], bool]] = None,
                 allowlist: Optional[list] = None,
                 dry_run: bool = False):
        """
        confirm_fn: callable(question:str) -> bool. If None, denies all CONFIRM
                    actions by default (safe). The daemon passes a voice prompt.
        dry_run:    if True, nothing is actually executed — only described.
        """
        self.confirm_fn = confirm_fn
        self.allowlist = [Path(p).resolve() for p in (allowlist or DEFAULT_ALLOWLIST)]
        self.dry_run = dry_run
        self._audit = []

    # ── Classification ──────────────────────────────────────────

    def classify(self, action: str, target: str = "") -> Risk:
        """Decide risk level of an action string + target path/command."""
        text = f"{action} {target}".lower()

        for pat in HARD_BLOCK:
            if re.search(pat, text):
                logger.error(f"🛑 BLOCKED (hard rule): {action} {target}")
                return Risk.BLOCK

        # Writing/deleting inside a protected system folder → block
        if target:
            try:
                tp = Path(target).expanduser().resolve()
                for prot in PROTECTED:
                    if str(tp).startswith(str(prot)):
                        # reading is fine, modifying is not
                        if any(k in text for k in ("delete", "remove", "rm", "write", "overwrite", "move")):
                            logger.error(f"🛑 BLOCKED (protected path): {tp}")
                            return Risk.BLOCK
            except Exception:
                pass

        if any(kw in text for kw in CONFIRM_KEYWORDS):
            return Risk.CONFIRM

        return Risk.SAFE

    # ── Gate ────────────────────────────────────────────────────

    def allow(self, action: str, target: str = "", reason: str = "") -> bool:
        """
        Main gate. Returns True if the action may proceed.
        SAFE → True. CONFIRM → ask confirm_fn. BLOCK → False.
        """
        risk = self.classify(action, target)
        self._log(action, target, risk, reason)

        if risk == Risk.BLOCK:
            return False
        if risk == Risk.SAFE:
            return True

        # CONFIRM
        question = self._confirm_question(action, target, reason)
        if self.confirm_fn is None:
            logger.warning(f"⚠️  No confirm handler — DENYING by default: {action} {target}")
            return False
        approved = bool(self.confirm_fn(question))
        logger.info(f"{'✅ Approved' if approved else '❌ Denied'}: {action} {target}")
        self._log(action, target, risk, f"user_{'approved' if approved else 'denied'}")
        return approved

    def _confirm_question(self, action: str, target: str, reason: str) -> str:
        q = f"I'm about to {action}"
        if target:
            q += f" {Path(target).name if '/' in target else target}"
        if reason:
            q += f" ({reason})"
        q += ". Should I proceed? Say yes or no."
        return q

    # ── Safe destructive operations ─────────────────────────────

    def is_in_allowlist(self, path: str) -> bool:
        try:
            p = Path(path).expanduser().resolve()
        except Exception:
            return False
        return any(str(p).startswith(str(a)) for a in self.allowlist)

    def safe_delete(self, path: str) -> dict:
        """Move to macOS Trash instead of permanent delete (undo-able)."""
        p = Path(path).expanduser()
        if not p.exists():
            return {"success": False, "error": "not found"}
        if not self.is_in_allowlist(str(p)):
            return {"success": False, "error": f"outside allowlist: {p}"}
        if self.dry_run:
            return {"success": True, "dry_run": True, "would_trash": str(p)}

        # Use macOS Finder to move to Trash (recoverable)
        try:
            script = f'tell application "Finder" to delete POSIX file "{p.resolve()}"'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
            logger.info(f"🗑  Trashed: {p}")
            return {"success": True, "trashed": str(p)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def safe_run(self, command: str, cwd: str = None, timeout: int = 30) -> dict:
        """Run a shell command only if it passes classification."""
        risk = self.classify("run command", command)
        if risk == Risk.BLOCK:
            return {"success": False, "blocked": True, "error": "dangerous command blocked"}
        if risk == Risk.CONFIRM and not self.allow("run command", command):
            return {"success": False, "denied": True}
        if self.dry_run:
            return {"success": True, "dry_run": True, "would_run": command}
        try:
            r = subprocess.run(command, shell=True, capture_output=True,
                               text=True, timeout=timeout, cwd=cwd)
            return {"success": r.returncode == 0, "stdout": r.stdout[:4000],
                    "stderr": r.stderr[:1000], "returncode": r.returncode}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"timeout {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def describe(self, action: str, target: str = "") -> str:
        """Dry-run description — what WOULD happen, without doing it."""
        risk = self.classify(action, target)
        return f"[{risk.value.upper()}] {action} {target}".strip()

    # ── Audit ───────────────────────────────────────────────────

    def _log(self, action: str, target: str, risk: Risk, reason: str):
        entry = {
            "action": action, "target": target[:200],
            "risk": risk.value, "reason": reason,
            "ts": datetime.now().isoformat()
        }
        self._audit.append(entry)
        try:
            existing = []
            if AUDIT_LOG.exists():
                existing = json.loads(AUDIT_LOG.read_text())
            existing.append(entry)
            AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
            AUDIT_LOG.write_text(json.dumps(existing[-1000:], indent=2))
        except Exception:
            pass

    def recent_audit(self, n: int = 20) -> list:
        return self._audit[-n:]


# ── Self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 55)
    print("🛡  SafetyLayer — Self Test")
    print("═" * 55)

    # Auto-approve confirmations for the test
    s = SafetyLayer(confirm_fn=lambda q: True)

    cases = [
        ("read", "~/Desktop/file.txt", Risk.SAFE),
        ("build a web app", "", Risk.SAFE),
        ("delete", "~/Desktop/old.txt", Risk.CONFIRM),
        ("send email", "boss@work.com", Risk.CONFIRM),
        ("git push", "origin main", Risk.CONFIRM),
        ("run command", "rm -rf /", Risk.BLOCK),
        ("run command", "sudo rm file", Risk.BLOCK),
        ("write", "/System/important", Risk.BLOCK),
    ]
    passed = 0
    for action, target, expected in cases:
        got = s.classify(action, target)
        ok = got == expected
        passed += ok
        print(f"  {'✅' if ok else '❌'} {action:14} {target:24} → {got.value} (want {expected.value})")
    print(f"\n{'🏆 ALL PASS' if passed == len(cases) else f'{passed}/{len(cases)}'}")

    # Confirm gate test
    print("\n--- Confirmation gate ---")
    denier = SafetyLayer(confirm_fn=lambda q: False)
    print(f"  delete denied → allow returns: {denier.allow('delete', '~/Desktop/x.txt')}")
    approver = SafetyLayer(confirm_fn=lambda q: True)
    print(f"  delete approved → allow returns: {approver.allow('delete', '~/Desktop/x.txt')}")
    print(f"  hard block → allow returns: {approver.allow('run command', 'rm -rf /')}")
