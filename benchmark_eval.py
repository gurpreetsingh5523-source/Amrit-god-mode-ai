"""Benchmark Evaluation — Single-pass vs Deep Reasoning comparison.

Tests deepseek-coder-v2:16b on coding + math + Punjabi questions.
Shows how AmritDeepReasoner (multi-loop) improves over single-pass.

Run:
    python benchmark_eval.py
    python benchmark_eval.py --subject coding
    python benchmark_eval.py --subject math
    python benchmark_eval.py --subject punjabi
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from datetime import datetime

from logger import setup_logger
from llm_router import LLMRouter

logger = setup_logger("BenchmarkEval")

MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
RESULTS_FILE = Path("workspace/benchmark_results.json")

# ─── Benchmark questions ──────────────────────────────────────────
BENCHMARK = {
    "coding": [
        {
            "q": "Write a Python function to check if a string is a palindrome.",
            "keywords": ["def", "return", "[::-1]", "=="],
            "expected": "def is_palindrome(s): return s == s[::-1]",
        },
        {
            "q": "Write a Python function to find duplicates in a list.",
            "keywords": ["def", "set()", "for", "return"],
            "expected": "Uses set or Counter to find duplicates",
        },
        {
            "q": "Fix this Python bug: `print(1/0)`",
            "keywords": ["ZeroDivisionError", "try", "except", "0"],
            "expected": "try/except ZeroDivisionError",
        },
        {
            "q": "Write a Python decorator that measures function execution time.",
            "keywords": ["def", "time", "wrapper", "return"],
            "expected": "Uses time.perf_counter, wraps function",
        },
        {
            "q": "Write a Python async function to run multiple coroutines concurrently.",
            "keywords": ["async", "await", "asyncio.gather"],
            "expected": "asyncio.gather(*coros)",
        },
    ],
    "math": [
        {
            "q": "What is 144 ÷ 12 × 3 + 7?",
            "keywords": ["43"],
            "expected": "43",
        },
        {
            "q": "Solve for x: 5x - 3 = 22",
            "keywords": ["x = 5", "5"],
            "expected": "x = 5",
        },
        {
            "q": "A train travels at 80 km/h for 2.5 hours. How far does it go?",
            "keywords": ["200"],
            "expected": "200 km",
        },
        {
            "q": "What is the sum of angles in a triangle?",
            "keywords": ["180"],
            "expected": "180 degrees",
        },
        {
            "q": "If 30% of a number is 90, what is the number?",
            "keywords": ["300"],
            "expected": "300",
        },
    ],
    "punjabi": [
        {
            "q": "ਪਾਈਥਨ ਵਿੱਚ 'for loop' ਕੀ ਕੰਮ ਕਰਦੀ ਹੈ? ਛੋਟੀ ਉਦਾਹਰਣ ਦਿਓ।",
            "keywords": ["for", "range", "print"],
            "expected": "for loop iterates over items",
        },
        {
            "q": "Git ਵਿੱਚ branch ਕਿਵੇਂ ਬਣਾਉਂਦੇ ਹਾਂ?",
            "keywords": ["git", "branch", "checkout", "-b"],
            "expected": "git checkout -b branch_name",
        },
        {
            "q": "API ਅਤੇ library ਵਿੱਚ ਕੀ ਫ਼ਰਕ ਹੈ?",
            "keywords": ["interface", "code", "function", "service"],
            "expected": "API is interface, library is reusable code",
        },
    ],
}


def score_response(response: str, keywords: list[str]) -> float:
    """Score 0.0–1.0 based on how many keywords appear in response."""
    if not response or len(response.strip()) < 10:
        return 0.0
    resp_lower = response.lower()
    hits = sum(1 for kw in keywords if kw.lower() in resp_lower)
    return round(hits / len(keywords), 2)


async def single_pass(router: LLMRouter, question: str) -> tuple[str, float]:
    """Single LLM call — no reasoning loops."""
    t0 = time.perf_counter()
    prompt = f"Answer concisely:\n{question}"
    response = await router.complete(prompt, max_tokens=300)
    elapsed = round(time.perf_counter() - t0, 2)
    return response or "", elapsed


async def deep_reasoning_pass(question: str) -> tuple[str, float]:
    """AmritDeepReasoner — multi-loop chain-of-thought."""
    from amrit_deep_reasoner import AmritDeepReasoner
    t0 = time.perf_counter()
    router = LLMRouter()
    reasoner = AmritDeepReasoner(llm_router=router)
    result = await reasoner.reason(question)
    elapsed = round(time.perf_counter() - t0, 2)
    answer = result.get("answer") or result.get("final_answer", "") if isinstance(result, dict) else str(result)
    return answer, elapsed


async def run_benchmark(subject: str | None = None) -> dict:
    """Run full benchmark. Returns results dict."""
    router = LLMRouter()
    subjects = [subject] if subject else list(BENCHMARK.keys())

    all_results = {}
    totals = {"single": {"score": 0, "time": 0, "n": 0},
              "deep":   {"score": 0, "time": 0, "n": 0}}

    for subj in subjects:
        questions = BENCHMARK.get(subj, [])
        subj_results = []
        print(f"\n{'═'*60}")
        print(f"  📋 Subject: {subj.upper()}  ({len(questions)} questions)")
        print(f"{'═'*60}")

        for i, item in enumerate(questions, 1):
            q = item["q"]
            kws = item["keywords"]
            print(f"\n  Q{i}: {q[:80]}{'...' if len(q) > 80 else ''}")

            # 1. Single-pass
            s_resp, s_time = await single_pass(router, q)
            s_score = score_response(s_resp, kws)

            # 2. Deep reasoning
            d_resp, d_time = await deep_reasoning_pass(q)
            d_score = score_response(d_resp, kws)

            improvement = round((d_score - s_score) * 100, 1)
            better = "🟢 better" if d_score > s_score else ("🔴 same/worse" if d_score < s_score else "🟡 equal")

            print(f"  ┌─ Single-pass  score={s_score:.2f} | {s_time}s")
            print(f"  │  {s_resp[:120].strip()}")
            print(f"  ├─ Deep reason  score={d_score:.2f} | {d_time}s  {better} ({improvement:+.0f}%)")
            print(f"  │  {d_resp[:120].strip()}")
            print(f"  └─ Keywords: {kws}")

            subj_results.append({
                "question": q,
                "keywords": kws,
                "expected": item["expected"],
                "single_pass": {"response": s_resp[:300], "score": s_score, "time_s": s_time},
                "deep_reason": {"response": d_resp[:300], "score": d_score, "time_s": d_time},
                "improvement_pct": improvement,
            })

            totals["single"]["score"] += s_score
            totals["single"]["time"]  += s_time
            totals["single"]["n"]     += 1
            totals["deep"]["score"]   += d_score
            totals["deep"]["time"]    += d_time
            totals["deep"]["n"]       += 1

        all_results[subj] = subj_results

    # ── Summary ───────────────────────────────────────────────────
    n = totals["single"]["n"] or 1
    avg_s = round(totals["single"]["score"] / n, 3)
    avg_d = round(totals["deep"]["score"]   / n, 3)
    avg_t_s = round(totals["single"]["time"] / n, 2)
    avg_t_d = round(totals["deep"]["time"]   / n, 2)
    win = sum(
        1 for subj in all_results
        for r in all_results[subj]
        if r["deep_reason"]["score"] > r["single_pass"]["score"]
    )

    summary = {
        "model": MODEL,
        "date": datetime.now().isoformat(),
        "total_questions": n,
        "single_pass":  {"avg_score": avg_s, "avg_time_s": avg_t_s},
        "deep_reasoning": {"avg_score": avg_d, "avg_time_s": avg_t_d},
        "deep_wins": win,
        "overall_improvement_pct": round((avg_d - avg_s) * 100, 1),
        "results": all_results,
    }

    print(f"\n{'═'*60}")
    print(f"  📊 FINAL SUMMARY")
    print(f"{'═'*60}")
    print(f"  Model         : {MODEL}")
    print(f"  Questions     : {n}")
    print(f"  Single-pass   : avg score={avg_s:.3f} | avg {avg_t_s}s/q")
    print(f"  Deep reasoning: avg score={avg_d:.3f} | avg {avg_t_d}s/q")
    print(f"  Deep wins     : {win}/{n} questions")
    print(f"  Improvement   : {summary['overall_improvement_pct']:+.1f}%")
    print(f"{'═'*60}\n")

    # Save
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"  💾 Results saved → {RESULTS_FILE}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark: single-pass vs deep reasoning")
    parser.add_argument("--subject", choices=["coding", "math", "punjabi"],
                        help="Test one subject only (default: all)")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.subject))
