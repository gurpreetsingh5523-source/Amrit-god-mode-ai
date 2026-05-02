"""Tiny HTTP server for Amrit God Mode Dashboard.

Serves dashboard.html and provides live API endpoints:
  GET /              → dashboard.html
  GET /api/logs      → last 40 lines from today's log file (JSON, ANSI stripped)
  GET /api/state     → workspace/state.json contents
  GET /api/memory    → summary of workspace JSON memory files
  GET /api/agents    → live agent status summary

Run:  python dashboard_server.py
Open:  http://localhost:7777
"""

import re
import json
import os
import http.server
import datetime
from pathlib import Path

PORT = 7777
BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "logs"
WS_DIR = BASE / "workspace"

# Strip ANSI escape codes from log lines
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_file(BASE / "dashboard.html", "text/html")
        elif self.path == "/api/logs":
            self._serve_logs()
        elif self.path == "/api/state":
            self._serve_json_file(WS_DIR / "state.json")
        elif self.path == "/api/memory":
            self._serve_memory_summary()
        elif self.path == "/api/agents":
            self._serve_agents()
        else:
            super().do_GET()

    def _serve_file(self, path, content_type):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def _serve_logs(self):
        today = datetime.date.today().isoformat()
        log_file = LOG_DIR / f"{today}.log"
        lines = []
        if log_file.exists():
            with open(log_file, "r", errors="replace") as f:
                all_lines = f.readlines()
                lines = [_ANSI_RE.sub("", line.rstrip()) for line in all_lines[-60:]]
        self._send_json({"lines": lines, "file": str(log_file.name)})

    def _serve_json_file(self, path):
        try:
            data = json.loads(path.read_text(errors="replace"))
            self._send_json(data)
        except (FileNotFoundError, json.JSONDecodeError):
            self._send_json({})

    def _serve_memory_summary(self):
        summary = {}
        for name in [
            "state.json", "experience.json", "failure_patterns.json",
            "evolution_log.json", "evolution_lessons.json",
            "knowledge_vectors.json", "learning_lessons.json",
            "pending_improvements.json", "training_metrics.json",
        ]:
            p = WS_DIR / name
            if p.exists():
                try:
                    d = json.loads(p.read_text(errors="replace"))
                    if isinstance(d, list):
                        summary[name] = {"type": "list", "count": len(d)}
                    elif isinstance(d, dict):
                        summary[name] = {"type": "dict", "keys": len(d)}
                    else:
                        summary[name] = {"type": type(d).__name__}
                except Exception:
                    summary[name] = {"type": "error"}
            else:
                summary[name] = {"type": "missing"}
        self._send_json(summary)

    def _send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_agents(self):
        """Return live agent status from state + recent log lines."""
        agents = [
            "planner", "coder", "researcher", "tester", "debugger",
            "tool", "memory", "upgrade", "monitor", "voice",
            "vision", "internet", "dataset", "simulation",
        ]
        state = {}
        try:
            state = json.loads((WS_DIR / "state.json").read_text(errors="replace"))
        except Exception:
            pass

        # Parse last 200 log lines to find recent agent activity
        today = datetime.date.today().isoformat()
        log_file = LOG_DIR / f"{today}.log"
        recent_agents: dict = {}
        if log_file.exists():
            try:
                lines = log_file.read_text(errors="replace").splitlines()[-200:]
                for ln in reversed(lines):
                    clean = _ANSI_RE.sub("", ln)
                    for ag in agents:
                        if ag not in recent_agents and ag.lower() in clean.lower():
                            status = "error" if "error" in clean.lower() or "❌" in clean else \
                                     "running" if "running" in clean.lower() else "idle"
                            recent_agents[ag] = status
                            break
            except Exception:
                pass

        result = []
        for ag in agents:
            result.append({
                "name": ag,
                "status": recent_agents.get(ag, "idle"),
                "last_task": state.get(f"{ag}:last_task", ""),
            })
        health = state.get("MonitorAgent:last_health", {})
        self._send_json({"agents": result, "health": health})

    def log_message(self, fmt, *args):
        pass  # silent


if __name__ == "__main__":
    os.chdir(str(BASE))
    with http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler) as srv:
        print(f"ੴ Amrit Dashboard → http://localhost:{PORT}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
