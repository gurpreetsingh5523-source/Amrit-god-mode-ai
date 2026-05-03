"""AMRIT AutoEvolve — ਤਿੰਨੇ modes ਦਾ ਇੱਕ autonomous loop.

ਹਰ cycle ਵਿੱਚ ਇਹ ਕੰਮ ਹੁੰਦੇ ਹਨ:

  Phase 1 — SELFFIX
    → ਸਾਰੇ .py files ਸਕੈਨ ਕਰੋ
    → bugs / bad patterns ਲੱਭੋ
    → DeepSeek ਨਾਲ fix ਕਰੋ
    → tests ਚਲਾਓ

  Phase 2 — LEARN (Internet Scraping)
    → GitHub trending Python repos scrape ਕਰੋ
    → ਨਵੇਂ patterns / snippets episodic memory ਵਿੱਚ ਸੇਵ ਕਰੋ
    → experience_log.json update ਕਰੋ

  Phase 3 — BENCHMARK
    → Coding + Math ਤੇ score ਕਰੋ
    → ਪਿਛਲੇ cycle ਨਾਲ compare ਕਰੋ
    → ਜੇ score ਘਟਿਆ → selffix ਦੁਬਾਰਾ

Usage:
    python main.py --mode autoevolve                # ਹਮੇਸ਼ਾ ਚੱਲੇ
    python main.py --mode autoevolve --cycles 3    # ਸਿਰਫ਼ 3 cycles
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from logger import setup_logger
from llm_router import LLMRouter

logger = setup_logger("AutoEvolve")

STATE_FILE  = Path("workspace/autoevolve_state.json")
RESULTS_DIR = Path("workspace/autoevolve_results")

# ── Import helpers ────────────────────────────────────────────────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(errors="replace"))
        except Exception:
            pass
    return {"cycles": 0, "last_score": {}, "history": []}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ══════════════════════════════════════════════════════════════════
# PHASE 1 — SELFFIX
# ══════════════════════════════════════════════════════════════════

async def phase_selffix(orchestrator) -> dict:
    """Run the existing selffix pipeline and return summary."""
    logger.info("🔧 Phase 1: SELFFIX ਸ਼ੁਰੂ...")
    t0 = time.perf_counter()
    result = {"fixed": 0, "errors": 0, "time_s": 0}
    try:
        from self_evolution import SelfEvolution
        evo = SelfEvolution(orchestrator)
        # Run 1 full cycle (analyze + fix + test)
        await evo.run(max_cycles=1)
        # Read evolution log for stats
        log_path = Path("workspace/evolution_log.json")
        if log_path.exists():
            log = json.loads(log_path.read_text(errors="replace"))
            entries = log if isinstance(log, list) else log.get("entries", [])
            recent = [e for e in entries if isinstance(e, dict)
                      and e.get("phase") in ("fix", "refactor")]
            result["fixed"] = len(recent)
    except Exception as exc:
        logger.error(f"Selffix error: {exc}")
        result["errors"] += 1
    result["time_s"] = round(time.perf_counter() - t0, 1)
    logger.info(f"  ✅ Selffix done — {result['fixed']} fixes | {result['time_s']}s")
    return result


# ══════════════════════════════════════════════════════════════════
# PHASE 2 — LEARN (scrape + memory)
# ══════════════════════════════════════════════════════════════════

async def phase_learn() -> dict:
    """Scrape GitHub trending + save patterns to episodic memory."""
    logger.info("🌐 Phase 2: LEARN ਸ਼ੁਰੂ (GitHub scraping)...")
    t0 = time.perf_counter()
    result = {"sources": 0, "snippets": 0, "errors": 0, "time_s": 0}

    # Target repos for coding patterns
    _REPOS = [
        "https://github.com/trending/python?since=daily",
        "https://raw.githubusercontent.com/vinta/awesome-python/master/README.md",
    ]

    try:
        from web_scraper import WebScraper
        scraper = WebScraper()
        all_text: list[str] = []

        for url in _REPOS:
            try:
                content = await scraper.scrape(url)
                if content and len(content) > 100:
                    all_text.append(content[:3000])
                    result["sources"] += 1
            except Exception as e:
                logger.warning(f"  Scrape failed {url}: {e}")

        if all_text:
            # Save to episodic memory
            try:
                from episodic_memory import EpisodicMemory
                mem = EpisodicMemory()
                combined = "\n\n---\n\n".join(all_text)
                await mem.store(
                    event_type="web_learning",
                    content=combined[:8000],
                    metadata={"source": "github_trending", "cycle_time": datetime.now().isoformat()}
                )
                result["snippets"] = len(all_text)
            except Exception as e:
                logger.warning(f"  Memory store failed: {e}")
                # Fallback — write to experience log directly
                exp_path = Path("workspace/experience.json")
                exp = []
                if exp_path.exists():
                    try:
                        exp = json.loads(exp_path.read_text(errors="replace"))
                    except Exception:
                        pass
                exp.append({
                    "type": "web_learning",
                    "ts": datetime.now().isoformat(),
                    "content": "\n".join(all_text)[:2000]
                })
                exp_path.parent.mkdir(exist_ok=True)
                exp_path.write_text(json.dumps(exp[-100:], ensure_ascii=False, indent=2))
                result["snippets"] = len(all_text)

    except Exception as exc:
        logger.error(f"Learn phase error: {exc}")
        result["errors"] += 1

    result["time_s"] = round(time.perf_counter() - t0, 1)
    logger.info(f"  ✅ Learn done — {result['sources']} sources | {result['snippets']} snippets | {result['time_s']}s")
    return result


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — BENCHMARK
# ══════════════════════════════════════════════════════════════════

async def phase_benchmark(router: LLMRouter) -> dict:
    """Run coding + math benchmark, return scores."""
    logger.info("📊 Phase 3: BENCHMARK ਸ਼ੁਰੂ...")
    t0 = time.perf_counter()
    result = {"coding": 0.0, "math": 0.0, "avg": 0.0, "time_s": 0}

    # Quick 3-question subset per subject (faster than full 5)
    QUICK = {
        "coding": [
            ("Write a Python function to reverse a string.",
             ["def", "return", "[::-1]"]),
            ("Fix this Python bug: `print(1/0)`",
             ["ZeroDivisionError", "try", "except"]),
            ("Write a Python function to check if a number is prime.",
             ["def", "return", "range"]),
        ],
        "math": [
            ("What is 144 ÷ 12 × 3 + 7?",       ["43"]),
            ("Solve for x: 5x - 3 = 22",          ["5"]),
            ("What is 25% of 320?",               ["80"]),
        ],
    }

    def _score(resp: str, kws: list[str]) -> float:
        if not resp or len(resp.strip()) < 5:
            return 0.0
        low = resp.lower()
        return round(sum(1 for k in kws if k.lower() in low) / len(kws), 2)

    scores: dict[str, list[float]] = {"coding": [], "math": []}

    for subj, questions in QUICK.items():
        for q, kws in questions:
            try:
                resp = await router.complete(
                    f"Answer concisely:\n{q}", max_tokens=200
                )
                scores[subj].append(_score(resp or "", kws))
            except Exception:
                scores[subj].append(0.0)

    result["coding"] = round(sum(scores["coding"]) / max(len(scores["coding"]), 1), 3)
    result["math"]   = round(sum(scores["math"])   / max(len(scores["math"]),   1), 3)
    result["avg"]    = round((result["coding"] + result["math"]) / 2, 3)
    result["time_s"] = round(time.perf_counter() - t0, 1)
    logger.info(f"  ✅ Benchmark — coding={result['coding']} math={result['math']} avg={result['avg']} | {result['time_s']}s")
    return result


# ══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════

class AmritAutoEvolve:
    """
    ਤਿੰਨੇ modes ਦਾ ਇੱਕ autonomous loop:
      selffix → learn → benchmark → ਦੁਬਾਰਾ
    """

    def __init__(self, orchestrator, max_cycles: int = 0):
        self.orchestrator = orchestrator
        self.max_cycles = max_cycles   # 0 = ਹਮੇਸ਼ਾ ਚੱਲੇ
        self.router = LLMRouter()
        self.state = _load_state()
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        cycle = self.state.get("cycles", 0)
        logger.info("☬ AMRIT AutoEvolve ਸ਼ੁਰੂ")
        logger.info(f"  ਪਿਛਲੇ cycles: {cycle} | max_cycles: {self.max_cycles or '∞'}")

        while True:
            cycle += 1
            ts = datetime.now().strftime("%H:%M:%S")
            logger.info(f"\n{'═'*56}")
            logger.info(f"  CYCLE {cycle}  [{ts}]")
            logger.info(f"{'═'*56}")

            cycle_result: dict = {"cycle": cycle, "ts": datetime.now().isoformat()}

            # ── Phase 1: Selffix ──────────────────────────────────
            sf = await phase_selffix(self.orchestrator)
            cycle_result["selffix"] = sf

            # ── Phase 2: Learn ────────────────────────────────────
            lrn = await phase_learn()
            cycle_result["learn"] = lrn

            # ── Phase 3: Benchmark ────────────────────────────────
            bm = await phase_benchmark(self.router)
            cycle_result["benchmark"] = bm

            # ── Compare with last cycle ───────────────────────────
            prev_avg = self.state.get("last_score", {}).get("avg", 0.0)
            delta    = round(bm["avg"] - prev_avg, 3)
            symbol   = "🟢" if delta > 0 else ("🔴" if delta < 0 else "🟡")

            logger.info(f"\n  {'─'*50}")
            logger.info(f"  Cycle {cycle} Summary:")
            logger.info(f"    Selffix  : {sf['fixed']} files fixed")
            logger.info(f"    Learn    : {lrn['sources']} sources scraped")
            logger.info(f"    Benchmark: avg={bm['avg']}  {symbol} ({delta:+.3f} vs prev)")
            logger.info(f"  {'─'*50}\n")

            # ── Save state ────────────────────────────────────────
            self.state["cycles"]     = cycle
            self.state["last_score"] = bm
            self.state["history"].append(cycle_result)
            self.state["history"] = self.state["history"][-20:]  # keep last 20
            _save_state(self.state)

            # ── Save per-cycle result ─────────────────────────────
            out = RESULTS_DIR / f"cycle_{cycle:04d}.json"
            out.write_text(json.dumps(cycle_result, ensure_ascii=False, indent=2))

            # ── Re-selffix if score dropped ───────────────────────
            if delta < -0.05:
                logger.warning(f"  ⚠️  Score ਘਟਿਆ {delta:+.3f} — extra selffix ਚਲਾ ਰਹੇ ਹਾਂ...")
                await phase_selffix(self.orchestrator)

            # ── Stop condition ────────────────────────────────────
            if self.max_cycles and cycle >= self.max_cycles:
                logger.info(f"  ✅ {cycle} cycles ਮੁਕੰਮਲ — ਰੁਕ ਰਹੇ ਹਾਂ")
                break

            # ── Wait before next cycle (10 min default) ──────────
            wait_s = 600
            logger.info(f"  💤 ਅਗਲਾ cycle {wait_s//60} ਮਿੰਟ ਵਿੱਚ...")
            await asyncio.sleep(wait_s)
