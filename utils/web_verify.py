"""
web_verify.py — Web Self-Verify & Self-Heal Loop
═══════════════════════════════════════════════════════════════════
DualBrain does test→fail→fix for PYTHON. This does the same for the
BROWSER: load HTML in a headless browser, capture JS/console errors +
failed network requests, and feed them back to the LLM to fix —
repeat until the page loads clean.

This is what lets Amrit build WORKING web apps autonomously instead of
producing code that silently crashes (e.g. the "THREE is not defined" bug).

Usage:
    from web_verify import verify_and_heal
    result = verify_and_heal("workspace/dashboard.html", max_rounds=3)
    # result: {ok, rounds, errors_fixed, final_errors, path}
"""

import asyncio
import re
from pathlib import Path
from logger import setup_logger

logger = setup_logger("WebVerify")


# ── Browser check: load HTML, collect console + page errors ──────────
async def inspect_page(html_path: str, wait_ms: int = 2500) -> dict:
    """Load an HTML file headless, return {errors, warnings, ok}."""
    from playwright.async_api import async_playwright

    errors: list[str] = []
    warnings: list[str] = []
    path = Path(html_path).resolve()
    if not path.exists():
        return {"ok": False, "errors": [f"file not found: {html_path}"], "warnings": []}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            page.on("console", lambda m: (
                errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error"
                else warnings.append(m.text) if m.type == "warning" else None
            ))
            page.on("pageerror", lambda e: errors.append(f"JS error: {e}"))
            page.on("requestfailed", lambda r: errors.append(
                f"failed request: {r.url} ({r.failure})" if r.failure else f"failed request: {r.url}"
            ))

            await page.goto(f"file://{path}", wait_until="load", timeout=15000)
            await page.wait_for_timeout(wait_ms)  # let scripts run / graph render

            # Heuristic: did the main container actually get content?
            body_len = await page.evaluate("document.body.innerText.length")
            canvas = await page.evaluate(
                "document.querySelectorAll('canvas').length"
            )

            await browser.close()

            # de-dup
            errors = list(dict.fromkeys(errors))
            return {"ok": len(errors) == 0, "errors": errors[:15],
                    "warnings": warnings[:5], "body_len": body_len, "canvas": canvas}
    except Exception as e:
        return {"ok": False, "errors": [f"browser failed: {e}"], "warnings": []}


# Known-blocked CDNs in headless Chromium → working replacements.
_CDN_SWAPS = [
    (r"https://cdnjs\.cloudflare\.com/ajax/libs/3d-force-graph/[0-9.]+/3d-force-graph(\.min)?\.js",
     "https://cdn.jsdelivr.net/npm/3d-force-graph"),
    (r"https://unpkg\.com/3d-force-graph[^\"']*", "https://cdn.jsdelivr.net/npm/3d-force-graph"),
    # Pinned old 3d-force-graph builds (e.g. @1.70.10) throw "undefined ... 'tick'".
    # Use the maintained latest build.
    (r"https://cdn\.jsdelivr\.net/npm/3d-force-graph@[0-9.]+/dist/3d-force-graph(?:\.min)?\.js",
     "https://cdn.jsdelivr.net/npm/3d-force-graph"),
]


def swap_blocked_cdns(html: str) -> str:
    """Deterministically replace ORB-blocked CDN URLs with working ones.
    Pure + testable — LLMs keep picking cdnjs for 3d-force-graph which is
    ERR_BLOCKED_BY_ORB in headless Chromium."""
    for pat, repl in _CDN_SWAPS:
        html = re.sub(pat, repl, html)
    return html


def fix_common_gotchas(html: str) -> str:
    """Deterministically fix recurring web-integration bugs BEFORE asking the LLM.
    Only CONSERVATIVE fixes that cannot backfire go here — context-dependent ones
    (e.g. three.js/three-spritetext version juggling) are left to the LLM heal
    which can see the whole file. Lesson learned: blindly stripping three.js
    breaks three-spritetext (needs a global THREE)."""
    html = swap_blocked_cdns(html)
    # GOTCHA: 3d-force-graph is a FACTORY — correct init is ForceGraph3D()(el).
    # LLMs often write ForceGraph3D(el) which silently fails to render (canvas=0,
    # no JS error). Rewrite the one-call form to the factory form.
    html = re.sub(r"ForceGraph3D\(\s*(?!\s*\))", "ForceGraph3D()(", html)
    # GOTCHA: `.cameraDistance(n)` is NOT a chainable method on the graph instance
    # (the real API is .cameraPosition({z:n})). LLMs chain it and the whole script
    # dies with "cameraDistance is not a function". Drop it from the chain so the
    # graph still renders with the default camera (conservative — only removes the
    # broken call, keeps the rest of the chain intact).
    html = re.sub(r"\.cameraDistance\s*\([^()]*\)", "", html)
    return html


def inspect_page_sync(html_path: str, wait_ms: int = 2500) -> dict:
    """Sync wrapper — safe to call even if an event loop is already running
    (runs in a separate thread in that case)."""
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False

    if not running:
        return asyncio.run(inspect_page(html_path, wait_ms))

    # A loop is already running → run in a dedicated thread with its own loop.
    import concurrent.futures
    def _run():
        return asyncio.run(inspect_page(html_path, wait_ms))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result(timeout=60)


# ── The self-heal loop ───────────────────────────────────────────────
def verify_and_heal(html_path: str, max_rounds: int = 3,
                    spec: str = "") -> dict:
    """
    Load → detect errors → LLM fix → repeat until clean or max_rounds.
    Returns {ok, rounds, errors_fixed, final_errors, path}.
    """
    from llm_client import LLMClient

    path = Path(html_path)
    if not path.exists():
        return {"ok": False, "error": f"not found: {html_path}"}

    fixer = LLMClient(system_prompt=(
        "You are a web debugging expert. You are given an HTML file with browser "
        "JS/console errors plus the error list. Fix ALL errors and return the "
        "COMPLETE corrected HTML.\n"
        "KNOWN GOTCHAS (apply when relevant):\n"
        "- For the 'tick'/'LinearFilter'/'SpriteText is not defined' family of errors: "
        "REMOVE three-spritetext, SpriteText and any nodeThreeObject usage entirely, "
        "and REMOVE any separate three.js <script>. Use ONLY 3d-force-graph's built-in "
        ".nodeLabel(n=>n.name) for labels (HTML tooltip, needs no global THREE). "
        "3d-force-graph bundles its own three internally.\n"
        "- Only call 3d-force-graph methods that REALLY exist (graphData, nodeLabel, "
        "nodeColor, nodeVal, linkColor, linkWidth, linkDirectionalParticles, "
        "linkDirectionalParticleSpeed/Width/Color, d3Force). Never invent methods "
        "like linkDirectionalParticleTailLength.\n"
        "- Use cdn.jsdelivr.net for 3d-force-graph (cdnjs file is ORB-blocked).\n"
        "- NEVER drive the camera on setInterval (it breaks user zoom/pan).\n"
        "- Ensure element IDs referenced in JS exist; graph container needs height.\n"
        "Return ONLY the full HTML, no markdown fences, no explanation."
    ))

    # Deterministic pre-fix: apply known gotcha fixes (CDN swap, drop duplicate
    # three.js) BEFORE the loop — cheaper + more reliable than asking the LLM.
    _src = path.read_text()
    _new = fix_common_gotchas(_src)
    if _new != _src:
        path.write_text(_new)
        logger.info("🔧 pre-fix: applied deterministic gotcha fixes")

    errors_fixed = 0
    for rnd in range(1, max_rounds + 1):
        report = inspect_page_sync(html_path)
        errs = report.get("errors", [])
        logger.info(f"🔍 Round {rnd}: {len(errs)} error(s), "
                    f"body_len={report.get('body_len')}, canvas={report.get('canvas')}")

        if report.get("ok") and report.get("body_len", 0) > 0:
            logger.info(f"✅ Page loads clean (round {rnd})")
            return {"ok": True, "rounds": rnd, "errors_fixed": errors_fixed,
                    "final_errors": [], "path": str(path),
                    "canvas": report.get("canvas", 0)}

        if not errs:
            # No console errors but page looks empty — note it, stop.
            logger.warning("⚠️  No console errors but page may be empty")
            return {"ok": False, "rounds": rnd, "errors_fixed": errors_fixed,
                    "final_errors": ["page rendered empty (no errors)"],
                    "path": str(path)}

        logger.info(f"🔧 Round {rnd}: asking LLM to fix {len(errs)} error(s)")
        for e in errs[:5]:
            logger.info(f"     • {e[:100]}")

        current = path.read_text()
        # keep prompt within budget
        prompt = (
            "This HTML file has browser errors. Fix them all.\n\n"
            "ERRORS:\n" + "\n".join(f"- {e}" for e in errs[:12]) + "\n\n"
            + (f"INTENT: {spec}\n\n" if spec else "")
            + f"CURRENT HTML:\n{current[:14000]}\n\n"
            "Return ONLY the complete fixed HTML."
        )
        fixed = fixer.complete(prompt, max_tokens=9000)
        fixed = re.sub(r'^```[a-zA-Z]*\n|```$', '', fixed.strip(), flags=re.MULTILINE).strip()

        if fixed and "<" in fixed and len(fixed) > 200:
            # backup + write
            path.with_suffix(path.suffix + f".r{rnd}.bak").write_text(current)
            path.write_text(fixed)
            errors_fixed += len(errs)
            logger.info(f"   ✏️  rewrote {path.name} ({len(fixed.splitlines())} lines)")
        else:
            logger.warning("   ⚠️  LLM fix was empty/invalid — keeping current")
            return {"ok": False, "rounds": rnd, "errors_fixed": errors_fixed,
                    "final_errors": errs, "path": str(path)}

    # final check
    final = inspect_page_sync(html_path)
    return {"ok": final.get("ok", False), "rounds": max_rounds,
            "errors_fixed": errors_fixed, "final_errors": final.get("errors", []),
            "path": str(path), "canvas": final.get("canvas", 0)}


# ── Self-test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Build a deliberately broken page to prove the loop heals it
    broken = """<!DOCTYPE html><html><head><title>t</title></head>
<body><div id="app"></div>
<script>
  // BUG: THREE is not defined (classic)
  const x = new THREE.SphereGeometry(1);
  document.getElementById('app').innerText = 'loaded';
</script></body></html>"""
    test_path = "workspace/_webverify_selftest.html"
    Path("workspace").mkdir(exist_ok=True)
    Path(test_path).write_text(broken)

    print("═" * 55)
    print("🔬 WebVerify self-test — broken page (THREE undefined)")
    print("═" * 55)
    r = inspect_page_sync(test_path)
    print(f"Detected errors: {len(r['errors'])}")
    for e in r["errors"]:
        print(f"  • {e[:90]}")
    print(f"\n{'✅ Error detection WORKS' if r['errors'] else '❌ no errors detected'}")
    Path(test_path).unlink(missing_ok=True)
