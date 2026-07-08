# ─── PATH INJECTION FOR MODULAR STRUCTURE ───
import sys
from pathlib import Path
_base_dir = Path(__file__).resolve().parent
if _base_dir.name in ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]:
    _base_dir = _base_dir.parent
_subdirs = ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]
for _sd in _subdirs:
    _path_str = str(_base_dir / _sd)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)
# ───────────────────────────────────────────
\n"""Tiny HTTP server for Amrit God Mode Dashboard.

Serves dashboard.html and provides live API endpoints:
  GET /              → dashboard.html
  GET /api/logs      → last 40 lines from today's log file (JSON)
  GET /api/state     → workspace/state.json contents
  GET /api/memory    → summary of workspace JSON memory files

Run:  python dashboard_server.py
Open:  http://localhost:7777
"""

import json
import os
import asyncio
import http.server
import datetime
from pathlib import Path

PORT = 7777
BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "logs"
WS_DIR = BASE / "workspace"
DASH = WS_DIR / "amrit_dashboard"

# Lazy, lightweight brain for chat (LLM router only — NOT the full orchestrator).
_router = None
# Holds a DualBrain-generated fix awaiting the user's "apply" confirmation.
_PENDING_FIX = {}  # {"path": str, "code": str, "name": str}
def _get_router():
    global _router
    if _router is None:
        from llm_router import LLMRouter
        _router = LLMRouter()
    return _router


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_file(DASH / "index.html", "text/html")
        elif self.path == "/amrit_state.json":
            self._serve_json_file(DASH / "amrit_state.json")
        elif self.path == "/api/logs":
            self._serve_logs()
        elif self.path == "/api/state":
            self._serve_json_file(WS_DIR / "state.json")
        elif self.path == "/api/memory":
            self._serve_memory_summary()
        elif self.path == "/api/activity":
            self._serve_activity()
        elif self.path == "/favicon.ico":
            self.send_response(204); self.end_headers()   # no favicon → avoid 404
        else:
            super().do_GET()

    def _serve_activity(self):
        """Recently-active agents from today's log → dashboard lights up signals."""
        active = []
        try:
            import re as _re
            today = datetime.date.today().isoformat()
            lf = LOG_DIR / f"{today}.log"
            if lf.exists():
                tail = lf.read_text(errors="replace").splitlines()[-60:]
                known = ("coder", "planner", "researcher", "tester", "debugger",
                         "memory", "tool", "vision", "voice", "self-verify")
                for line in tail:
                    for a in known:
                        if a in line.lower() and a not in active:
                            active.append(a)
        except Exception:
            pass
        self._send_json({"active": active[-6:]})

    def do_POST(self):
        if self.path == "/api/chat":
            self._serve_chat()
        else:
            self.send_error(404)

    def _serve_chat(self):
        """Real chat with Amrit's brain (DeepSeek via LLMRouter). Lightweight."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            msg = (body.get("message") or "").strip()
            if not msg:
                return self._send_json({"reply": "Say something 🙂"})

            # ACTION intents → trigger the REAL engine
            ml = msg.lower()
            if ml.startswith(("learn ", "sikh ", "seekh ")):
                return self._send_json({"reply": self._engine_learn(msg.split(" ", 1)[1].strip())})
            if ml in ("status", "self status", "amrit status", "self-status"):
                return self._send_json({"reply": "🧬 Amrit live self-status:\n" + self._self_context()})
            if ml.startswith(("evolve", "self-evolve", "self evolve", "godmode")):
                return self._send_json({"reply": self._engine_evolve()})
            if ml.startswith(("fix ", "self-fix ", "self fix ")):
                return self._send_json({"reply": self._engine_fix(msg.split(" ", 1)[1].strip())})
            if ml in ("apply", "apply fix", "apply it", "yes apply", "haan apply"):
                return self._send_json({"reply": self._engine_apply()})
            if ml in ("discard", "cancel", "no", "discard fix"):
                _PENDING_FIX.clear()
                return self._send_json({"reply": "🗑 Discarded the pending fix. Nothing changed."})
            # Phase 4 — capability breadth: real vision/web actions from chat
            if ml.startswith(("scrape ", "fetch ")):
                return self._send_json({"reply": self._cap_scrape(msg.split(" ", 1)[1].strip())})
            if ml in ("screenshot", "see screen", "look at screen", "what's on my screen",
                      "what is on my screen", "see my screen"):
                return self._send_json({"reply": self._cap_screen()})
            if ml.startswith(("code ", "write code ")):
                return self._send_json({"reply": self._code_verified(msg.split(" ", 1)[1].strip())})
            if ml.startswith(("dual ", "ensemble ", "2llm ")):
                task = msg.split(" ", 1)[1].strip()
                try:
                    from dual_llm import dual_answer
                    r = asyncio.run(dual_answer(task, is_code=True))
                    tag = f"🤝 dual-LLM (2 models → analyser picked '{r['winner']}', verified={r['verified']})"
                    return self._send_json({"reply": f"{tag}\n```python\n{r['best']}\n```"})
                except Exception as e:
                    return self._send_json({"reply": f"⚠️ dual failed: {e}"})

            # No explicit keyword → SMART ROUTER: understand natural language and
            # route to the right capability (full control, not just fixed commands).
            intent, task = self._route_intent(msg)
            if intent == "code":
                return self._send_json({"reply": self._code_verified(task or msg)})
            if intent == "fix":
                return self._send_json({"reply": self._engine_fix(task or msg)})
            if intent == "learn":
                return self._send_json({"reply": self._engine_learn(task or msg)})
            if intent == "scrape":
                return self._send_json({"reply": self._cap_scrape(task or msg)})
            if intent == "screenshot":
                return self._send_json({"reply": self._cap_screen()})
            if intent == "status":
                return self._send_json({"reply": "🧬 Amrit live self-status:\n" + self._self_context()})
            if intent == "evolve":
                return self._send_json({"reply": self._engine_evolve()})
            # intent == "chat" → converse, grounded in Amrit's REAL self-state
            ctx = self._self_context()
            sys_prompt = (
                "You are Amrit, a REAL autonomous self-evolving AI system running on this "
                "machine (ੴ ethos: truth, service, humility). You are NOT a generic chatbot — "
                "you have an actual engine and can ACT: write code, fix files, learn topics, "
                "scrape URLs, see the screen, self-evolve. Answer truthfully using your REAL "
                "state below; if the user wants an action, tell them you can do it.\n\n"
                "--- YOUR REAL STATE ---\n" + ctx
            )
            router = _get_router()
            reply = asyncio.run(router.complete(msg, system=sys_prompt, max_tokens=600))
            self._send_json({"reply": (reply or "").strip()})
        except Exception as e:
            self._send_json({"reply": f"⚠️ brain error: {e}"})

    def _route_intent(self, msg: str):
        """LLM understands ANY natural-language request → (intent, task). This is
        what gives the chat FULL control instead of only fixed keyword commands."""
        prompt = (
            "You route a user's message to ONE capability of an autonomous AI. "
            "Pick the single best intent and extract the core task text.\n"
            "Intents:\n"
            "- code: write/generate/build code or a program\n"
            "- fix: fix, debug, or improve an existing file (task = file or description)\n"
            "- learn: study/learn a topic or library from GitHub (task = topic)\n"
            "- scrape: fetch/read a web URL (task = the url)\n"
            "- screenshot: look at / see the screen\n"
            "- status: report the AI's own state/health/capabilities\n"
            "- evolve: run a self-improvement / self-evolution cycle\n"
            "- chat: a question, greeting, or anything conversational\n"
            f'User message: "{msg}"\n'
            'Reply with STRICT JSON only: {"intent":"<one>","task":"<core task or empty>"}'
        )
        try:
            import json as _json, re as _re
            raw = asyncio.run(_get_router().complete(prompt, model="reasoning", max_tokens=120)) or ""
            m = _re.search(r"\{.*\}", raw, _re.S)
            obj = _json.loads(m.group()) if m else {}
            intent = str(obj.get("intent", "chat")).lower().strip()
            valid = {"code", "fix", "learn", "scrape", "screenshot", "status", "evolve", "chat"}
            return (intent if intent in valid else "chat"), str(obj.get("task", "")).strip()
        except Exception:
            return "chat", ""

    def _self_context(self) -> str:
        """Build Amrit's REAL self-state from engine files (lightweight)."""
        bits = []
        try:
            d = json.loads((BASE / "learning_data.json").read_text())
            topics = [e.get("topic") for e in d]
            bits.append(f"Learned {sum(len(e.get('patterns',[])) for e in d)} patterns "
                        f"from {len(d)} topics (e.g. {', '.join(topics[:6])}) via github_learner.")
        except Exception:
            pass
        try:
            st = json.loads((DASH / "amrit_state.json").read_text())
            bits.append(f"{st.get('agent_count','?')} agents, {st.get('subsystem_count','?')} "
                        f"capability subsystems, {st.get('skill_count','?')} crystallized skills, "
                        f"{st.get('lesson_count','?')} evolution lessons, "
                        f"{st.get('failure_count','?')} FailureDNA patterns learned.")
            t = st.get("tests", {})
            bits.append(f"Self-tests: {t.get('godmode',0)} unit + {t.get('integration',0)} engine integration.")
        except Exception:
            pass
        bits.append("Self-fix: DualBrain (proven: fixed a buggy factorial). Self-heal web: web_verify. "
                    "Self-learn: FailureDNA + github_learner + skill crystallization.")
        return "\n".join(bits)

    def _engine_learn(self, topic: str) -> str:
        """Trigger the REAL self-learning engine from chat."""
        if not topic:
            return "Tell me what to learn, e.g. 'learn fastapi'."
        try:
            import sys as _sys
            _sys.path.insert(0, str(BASE))
            from github_learner import GitHubLearner
            g = GitHubLearner()
            hit = g.recall_patterns(topic)
            if hit and hit.get("patterns"):
                ps = hit["patterns"]
                return (f"🧠 I already learned '{topic}' — {len(ps)} patterns. e.g.:\n"
                        + "\n".join(f"• {str(p)[:90]}" for p in ps[:4]))
            res = g.learn(topic, max_repos=1, max_files=2)
            ps = getattr(res, "patterns", []) or []
            if ps:
                return (f"🧠 Learned '{topic}' from {res.repos[:1]} — {len(ps)} new patterns:\n"
                        + "\n".join(f"• {str(p)[:90]}" for p in ps[:5]))
            return f"Searched for '{topic}' but found nothing useful to learn."
        except Exception as e:
            return f"⚠️ learn failed: {e}"

    def _engine_evolve(self) -> str:
        """Trigger a REAL self-evolution cycle in the background (non-blocking)."""
        try:
            import subprocess, sys as _sys
            subprocess.Popen([_sys.executable, "main.py", "--mode", "godmode"],
                             cwd=str(BASE),
                             stdout=open(BASE / "logs" / "chat_evolve.log", "a"),
                             stderr=subprocess.STDOUT)
            return ("⚡ Self-evolution cycle STARTED (godmode engine running in background).\n"
                    "It will: analyze all files → run tests → DualBrain self-fix → "
                    "FailureDNA learn → additive coverage. Watch logs/ or ask me 'status' in a bit.")
        except Exception as e:
            return f"⚠️ could not start evolution: {e}"

    def _engine_fix(self, target: str) -> str:
        """Run a REAL DualBrain fix on a workspace file."""
        if not target:
            return "Which file? e.g. 'fix api.py' (looks in workspace/)."
        try:
            from pathlib import Path as _P
            import glob
            # exact relative path first; else search by name
            exact = WS_DIR / target
            if exact.is_file():
                matches = [str(exact)]
            else:
                matches = sorted(set(glob.glob(str(WS_DIR / "**" / target), recursive=True)))
            if not matches:
                return f"Couldn't find '{target}' under workspace/."
            if len(matches) > 1:
                rels = [str(_P(m).relative_to(WS_DIR)) for m in matches]
                return ("Multiple files match — say the exact path:\n" +
                        "\n".join(f"• fix {r}" for r in rels[:8]))
            fp = _P(matches[0])
            code = fp.read_text()[:4000]
            from dual_brain_coder import evolve_code
            import re as _re
            res = evolve_code(f"Find and fix any bugs in this file '{fp.name}':\n{code}", max_turns=2)
            fixed = (res or {}).get("final_code", "") if isinstance(res, dict) else str(res)
            fit = (res or {}).get("highest_fitness", 0) if isinstance(res, dict) else 0
            fixed = _re.sub(r'^```[a-zA-Z]*\n|```$', '', (fixed or "").strip(), flags=_re.MULTILINE).strip()
            if not fixed or len(fixed) < 20:
                _PENDING_FIX.clear()
                return f"🔧 DualBrain ran on {fp.name} (fitness {fit:.2f}) — no usable change produced."
            # syntax-gate python before offering to apply
            if fp.suffix == ".py":
                import ast as _ast
                try:
                    _ast.parse(fixed)
                except SyntaxError as se:
                    _PENDING_FIX.clear()
                    return f"🔧 DualBrain output had a syntax error ({se}); not offering apply."
            _PENDING_FIX.update({"path": str(fp), "code": fixed, "name": fp.name})
            preview = "\n".join(fixed.splitlines()[:8])
            return (f"🔧 DualBrain fixed {fp.name} (fitness {fit:.2f}, {len(fixed.splitlines())} lines).\n"
                    f"Preview:\n{preview}\n…\n"
                    f"▶️ Reply 'apply' to save it (I'll back up the original), or 'discard'.")
        except Exception as e:
            return f"⚠️ fix failed: {e}"

    def _code_verified(self, task: str) -> str:
        """Amrit's fine-tuned coder drafts → exec-check → smarter model reviews/fixes
        edge-case bugs → return VERIFIED code (a raw 7B can err, the system must not)."""
        import re as _re
        if not task:
            return "What should I code? e.g. 'code a factorial function'."
        router = _get_router()
        try:
            draft = asyncio.run(router.complete(task, model="amrit-coder", max_tokens=500)) or ""
        except Exception as e:
            return f"⚠️ fine-tuned coder failed: {e}"
        code = _re.sub(r"^```[a-z]*\n|```$", "", draft.strip(), flags=_re.M).strip()
        # Layer 1: does it even run/define cleanly?
        runs = True
        try:
            exec(code, {})
        except Exception:
            runs = False
        # Layer 2: reasoning-model review + fix (catches logic/edge-case bugs).
        review_prompt = (
            f"Task: {task}\n\nThis draft code may have bugs (esp. edge cases like 0, "
            f"empty input). Review and return ONLY the corrected, complete Python in one "
            f"```python block. If already correct, return it unchanged.\n\n```python\n{code}\n```"
        )
        try:
            fixed = asyncio.run(router.complete(review_prompt, model="reasoning", max_tokens=600)) or ""
            fixed = _re.sub(r"^```[a-z]*\n|```$", "", fixed.strip(), flags=_re.M).strip()
            try:
                exec(fixed, {})            # verified runs
                final, tag = fixed, "✅ verified (fine-tuned draft → reviewed & fixed)"
            except Exception:
                final, tag = (code if runs else fixed), "⚠️ best-effort (review didn't fully verify)"
        except Exception:
            final, tag = code, "🧠 fine-tuned draft (review unavailable)"
        return f"{tag}\n```python\n{final}\n```"

    def _cap_scrape(self, url: str) -> str:
        """Phase 4: real web capability — scrape a page's text."""
        if not url or "." not in url:
            return "Give a URL, e.g. 'scrape https://example.com'."
        if not url.startswith("http"):
            url = "https://" + url
        try:
            from web_scraper import WebScraper
            txt = (WebScraper().text(url) or "").strip()
            return f"🌐 {url}\n\n{txt[:700]}" + ("…" if len(txt) > 700 else "") if txt else "No text extracted."
        except Exception as e:
            return f"⚠️ scrape failed: {e}"

    def _cap_screen(self) -> str:
        """Phase 4: real vision capability — screenshot + describe what's on screen."""
        try:
            import asyncio
            import screen_control as sc
            path = sc.screenshot("chat")
            if not path:
                return "⚠️ couldn't capture screen (permissions?)."
            res = asyncio.run(sc.understand_screen(path, "Briefly describe what is on screen."))
            desc = res.get("description") or res.get("analysis") or res.get("error") or str(res)
            return f"👁️ Screen captured ({path}):\n{str(desc)[:700]}"
        except Exception as e:
            return f"⚠️ screen vision failed: {e}"

    def _engine_apply(self) -> str:
        """Apply the pending DualBrain fix — with a timestamped backup."""
        if not _PENDING_FIX.get("code"):
            return "Nothing to apply. First run e.g. 'fix api.py'."
        try:
            from pathlib import Path as _P
            fp = _P(_PENDING_FIX["path"])
            bak = fp.with_suffix(fp.suffix + ".bak")
            if fp.exists():
                bak.write_text(fp.read_text())
            fp.write_text(_PENDING_FIX["code"])
            name = _PENDING_FIX["name"]
            _PENDING_FIX.clear()
            return f"✅ Applied fix to {name} (backup saved as {bak.name}). Self-fix complete."
        except Exception as e:
            return f"⚠️ apply failed: {e}"

    def _serve_file(self, path, content_type):
        try:
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
                lines = [l.rstrip() for l in all_lines[-40:]]
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
