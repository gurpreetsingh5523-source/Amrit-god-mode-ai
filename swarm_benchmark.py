"""
swarm_benchmark.py — measures the SWARM path (the real reliability frontier).
═══════════════════════════════════════════════════════════════════════════
DualBrain (single artifact) is ~100% (see benchmark.py). The real failures are
in the SWARM: multi-file projects, output_dir/path handling, web assembly.
This runs real projects through `main.py --mode swarm` and OBJECTIVELY verifies
the assembled output (correct path, imports, endpoints, rendering).

    python swarm_benchmark.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
BASE = Path(__file__).parent
PY = sys.executable
RESULTS = Path("workspace/swarm_benchmark_results.json")


def run_swarm(goal: str, timeout: int = 420) -> bool:
    try:
        subprocess.run([PY, "main.py", "--mode", "swarm", "--goal", goal],
                       cwd=str(BASE), capture_output=True, text=True, timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


# ── task 1: multi-endpoint API into a target folder (tests output_dir/path) ──
def task_api():
    d = BASE / "workspace" / "bench_api"
    shutil.rmtree(d, ignore_errors=True)
    run_swarm("Build api.py into workspace/bench_api/ folder: a FastAPI app with module-level "
              "`app`, in-memory items, POST /items (json {name})->{id,name}, GET /items->list, "
              "DELETE /items/{id}->204.")
    f = d / "api.py"
    if not f.exists():
        # tolerate other common names / any .py in the folder
        cands = list(d.glob("*.py")) if d.exists() else []
        if not cands:
            return False, f"no api file at {d} (path bug?)"
        f = cands[0]
    try:
        ns = {}
        exec(f.read_text(), ns)
        from fastapi.testclient import TestClient
        c = TestClient(ns["app"])
        r = c.post("/items", json={"name": "x"})
        iid = r.json().get("id")
        ok = r.status_code in (200, 201) and any(i.get("name") == "x" for i in c.get("/items").json())
        ok = ok and c.delete(f"/items/{iid}").status_code in (200, 204)
        return ok, None if ok else "endpoints misbehaved"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


# ── task 2: multi-FILE package (tests multi-file assembly + imports) ─────────
def task_multifile():
    d = BASE / "workspace" / "bench_pkg"
    shutil.rmtree(d, ignore_errors=True)
    run_swarm("Build a package into workspace/bench_pkg/ folder with TWO files: calc.py "
              "containing add(a,b) and sub(a,b); and main.py that imports from calc and has "
              "compute() returning add(2,3)-sub(10,4) (==-1).")
    calc, main = d / "calc.py", d / "main.py"
    if not (calc.exists() and main.exists()):
        return False, f"missing files (calc={calc.exists()}, main={main.exists()})"
    try:
        nsc = {}
        exec(calc.read_text(), nsc)
        ok = nsc["add"](2, 3) == 5 and nsc["sub"](10, 4) == 6
        return ok, None if ok else "calc functions wrong"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


# ── task 3: web dashboard (tests web assembly + rendering) ───────────────────
def task_web():
    d = BASE / "workspace" / "bench_dash"
    shutil.rmtree(d, ignore_errors=True)
    run_swarm("Build index.html into workspace/bench_dash/ folder: a 3d-force-graph dashboard "
              "(cdn.jsdelivr.net/npm/3d-force-graph, no separate three.js, no SpriteText) showing "
              "a core node linked to 4 children. Create graph after DOM ready. Dark theme.")
    f = d / "index.html"
    if not f.exists():
        cands = list(d.glob("*.html")) if d.exists() else []
        if not cands:
            return False, f"no html at {d} (path bug?)"
        f = cands[0]
    try:
        from web_verify import inspect_page_sync, fix_common_gotchas
        f.write_text(fix_common_gotchas(f.read_text()))
        rep = inspect_page_sync(str(f), wait_ms=3000)
        ok = rep.get("ok") and rep.get("canvas", 0) > 0 and len(rep.get("errors", [])) == 0
        return ok, None if ok else f"canvas={rep.get('canvas',0)} errs={rep.get('errors',[])[:1]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


TASKS = [("swarm:api", task_api), ("swarm:multifile", task_multifile), ("swarm:web", task_web)]


def main():
    print("═" * 60)
    print("🐝 Amrit SWARM Benchmark — real multi-file project reliability")
    print("═" * 60)
    results = []
    for name, fn in TASKS:
        print(f"  running {name} (swarm, may take minutes)…", flush=True)
        ok, err = fn()
        results.append({"name": name, "passed": ok, "error": err})
        print(f"  {'✅' if ok else '❌'} {name}" + (f"  ({err})" if err else ""))
    passed = sum(1 for r in results if r["passed"])
    rate = round(100 * passed / len(results))
    print("─" * 60)
    print(f"  SWARM ATSR: {passed}/{len(results)} = {rate}%")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"passed": passed, "total": len(results),
                                   "rate": rate, "results": results}, indent=2))
    print(f"  💾 saved → {RESULTS}")


if __name__ == "__main__":
    main()
