"""Tool Agent — File I/O, terminal, git, JSON operations with EthicalGuard enforcement."""
import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import TYPE_CHECKING
from toolbox import ToolBox
from toolbox_persistence import ToolBoxPersistence

if TYPE_CHECKING:
    from base_agent import BaseAgent  # type: ignore
else:
    # Fallback BaseAgent stub for environments where agents.base_agent is unavailable.
    class BaseAgent:
        def __init__(self, name, eb=None, state=None):
            self.name = name
            self.eb = eb
            self.state = state

        async def report(self, msg):
            # minimal async reporter used by callers
            return None

        def ok(self, **kwargs):
            return {"success": True, **kwargs}

        def err(self, msg):
            return {"success": False, "error": msg}

from ethical_guard import EthicalGuard

BLOCKED = ["rm -rf /","mkfs","dd if=/dev/zero",":(){ :|:& };:"]


class ToolAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("ToolAgent", eb, state)
        Path("workspace").mkdir(exist_ok=True)
        self.workspace = Path("workspace").resolve()
        self.guard = EthicalGuard()
        # ToolBox integration
        self.toolbox = ToolBox()
        self.toolbox_persistence = ToolBoxPersistence()
        # Load dynamic tools
        for name, desc in self.toolbox_persistence.load_tools().items():
            self.toolbox.create_tool(name, desc)
        # Wire proper FileOps and TerminalOps implementations
        try:
            from file_ops import FileOps
            self._file_ops = FileOps("workspace")
        except Exception:
            self._file_ops = None
        try:
            from terminal_ops import TerminalOps
            self._terminal_ops = TerminalOps()
        except Exception:
            self._terminal_ops = None
    def save_dynamic_tools(self):
        self.toolbox_persistence.save_tools(self.toolbox.tools)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        tool = d.get("tool","file")
        await self.report(f"Tool [{tool}:{d.get('action','')}]")
        # Support dynamic tools
        if tool in self.toolbox.tools:
            result = self.toolbox.run(tool)
            self.save_dynamic_tools()
            return self.ok(result=result, tool=tool)
        return await {"file": self._file, "terminal": self._terminal,
                      "git": self._git, "json": self._json,
                      "dir": self._dir, "search": self._search_files,
                      "run_python": self._run_python}.get(tool, self._file)(d)

    def _resolve_workspace_path(self, path_str: str) -> Path:
        """Resolve a given path string strictly inside the workspace directory.
        Always treat the provided path as relative to the workspace root.
        """
        # Normalize empty paths to workspace root
        if not path_str:
            return self.workspace
        candidate = (self.workspace / Path(path_str)).resolve()
        # Ensure candidate is within workspace
        ws = str(self.workspace)
        cand = str(candidate)
        if not (cand == ws or cand.startswith(ws + os.sep)):
            raise PermissionError("outside_workspace")
        return candidate

    async def _file(self, d):
        a = d.get("action","read")
        raw_path = d.get("path","")
        content = d.get("content","")

        # Resolve path strictly inside workspace
        try:
            p = self._resolve_workspace_path(raw_path)
        except PermissionError:
            return self.err("Action FAILED: Cannot access files outside the workspace directory")

        # Ethical check on file actions (brief description)
        safe, reason = self.guard.check(f"file.{a} {raw_path}")
        if not safe:
            return self.err(f"Action FAILED: Blocked by EthicalGuard because {reason}. Find a safer alternative.")

        if a == "read":
            if not p.exists():
                return self.err(f"Not found: {p}")
            # If caller asked to read a directory, return a listing instead of
            # attempting to read it as a file (which raises IsADirectoryError).
            if p.is_dir():
                return self.ok(files=[str(x) for x in p.iterdir()], path=str(p))
            return self.ok(content=p.read_text(errors="ignore"), path=str(p))
        if a == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return self.ok(path=str(p), size=len(content))
        if a == "append":
            with open(p,"a") as f:
                f.write(content)
            return self.ok(path=str(p))
        if a == "delete":
            if p.exists():
                p.unlink()
            return self.ok(deleted=str(p))
        if a == "list":
            if not p.exists():
                return self.err("Dir not found")
            return self.ok(files=[str(x) for x in p.iterdir()])
        if a == "exists":
            return self.ok(exists=p.exists(), path=str(p))
        if a == "copy":
            # Ensure destination is also inside workspace
            dest_raw = d.get("dest","")
            try:
                dest = self._resolve_workspace_path(dest_raw)
            except PermissionError:
                return self.err("Action FAILED: Cannot access files outside the workspace directory")
            shutil.copy2(p, dest)
            return self.ok(done=True)
        return self.err(f"Unknown action: {a}")

    async def _terminal(self, d):
        cmd = d.get("command","")
        # Wheelhouse blocked patterns first
        if any(b in cmd for b in BLOCKED):
            return self.err("Action FAILED: Blocked by EthicalGuard because blocked pattern detected. Find a safer alternative.")

        # EthicalGuard check on the full command
        safe, reason = self.guard.check(cmd)
        if not safe:
            return self.err(f"Action FAILED: Blocked by EthicalGuard because {reason}. Find a safer alternative.")

        await self.report(f"$ {cmd}")
        try:
            r = subprocess.run(cmd,shell=True,capture_output=True,text=True,
                               timeout=d.get("timeout",30),cwd=d.get("cwd","."))
            return self.ok(stdout=r.stdout[:3000],stderr=r.stderr[:1000],
                           returncode=r.returncode,success=r.returncode==0)
        except subprocess.TimeoutExpired:
            return self.err("Timeout")
        except Exception as e:
            return self.err(str(e))

    async def _git(self, d):
        a, repo = d.get("action","status"), d.get("repo",".")
        cmds = {"status":f"git -C {repo} status -s","log":f"git -C {repo} log --oneline -10",
                "add":f"git -C {repo} add {d.get('files','.')}",
                "commit":f'git -C {repo} commit -m "{d.get("message","auto-commit")}"',
                "push":f"git -C {repo} push","pull":f"git -C {repo} pull",
                "diff":f"git -C {repo} diff","init":f"git -C {repo} init",
                "clone":f"git clone {d.get('url','')} {d.get('dest','')}"}
        cmd = cmds.get(a)
        return await self._terminal({"command": cmd}) if cmd else self.err(f"Unknown git action: {a}")

    async def _json(self, d):
        a, raw_path = d.get("action","read"), d.get("path","data.json")
        try:
            p = self._resolve_workspace_path(raw_path)
        except PermissionError:
            return self.err("Action FAILED: Cannot access files outside the workspace directory")

        if a == "read":
            return self.ok(data=json.loads(p.read_text())) if p.exists() else self.err("Not found")
        if a in ("write","merge"):
            p.parent.mkdir(parents=True, exist_ok=True)
            existing = json.loads(p.read_text()) if a=="merge" and p.exists() else {}
            existing.update(d.get("data",{}))
            p.write_text(json.dumps(existing,indent=2))
            return self.ok(path=str(p))
        return self.err(f"Unknown: {a}")

    async def _dir(self, d):
        a, raw_path = d.get("action","list"), d.get("path",".")
        try:
            p = self._resolve_workspace_path(raw_path)
        except PermissionError:
            return self.err("Action FAILED: Cannot access files outside the workspace directory")

        if a == "create":
            p.mkdir(parents=True, exist_ok=True)
            return self.ok(path=str(p))
        if a == "delete":
            shutil.rmtree(p, ignore_errors=True)
            return self.ok(deleted=str(p))
        if a == "list":
            return self.ok(items=[{"name":x.name,"type":"dir"if x.is_dir() else "file"}
                                   for x in p.iterdir()]) if p.exists() else self.err("Not found")
        if a == "tree":
            lines = ["  "*len(x.relative_to(p).parts)+("📁 "if x.is_dir() else "📄 ")+x.name
                     for x in p.rglob("*")]
            return self.ok(tree="\n".join(lines))
        return self.err(f"Unknown: {a}")

    async def _search_files(self, d):
        """Search for text across workspace files. Uses FileOps.search_text()."""
        query = d.get("query", "")
        ext = d.get("extension", ".py")
        if not query:
            return self.err("No query provided")
        if self._file_ops:
            matches = self._file_ops.search_text(query, ext)
            return self.ok(query=query, matches=matches, count=len(matches))
        # Fallback: basic grep
        import subprocess
        r = subprocess.run(
            ["grep", "-rn", "--include", f"*{ext}", query, "workspace"],
            capture_output=True, text=True, timeout=10
        )
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()][:50]
        return self.ok(query=query, matches=lines, count=len(lines))

    async def _run_python(self, d):
        """Execute a Python code snippet safely via TerminalOps."""
        code = d.get("code", "")
        if not code:
            return self.err("No code provided")
        safe, reason = self.guard.check(code)
        if not safe:
            return self.err(f"Action FAILED: Blocked by EthicalGuard because {reason}.")
        if self._terminal_ops:
            result = self._terminal_ops.run_python(code, timeout=d.get("timeout", 15))
            return self.ok(**result)
        return self.err("TerminalOps not available")

