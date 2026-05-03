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
        print_header(subj, len(questions))

        for i, item in enumerate(questions, 1):
            q = item["q"]
            kws = item["keywords"]
            print_question(i, q)

            s_resp, s_time = await single_pass(router, q)
            s_score = score_response(s_resp, kws)

            d_resp, d_time = await deep_reasoning_pass(q)
            d_score = score_response(d_resp, kws)

            improvement = calculate_improvement(s_score, d_score)
            better = determine_better(s_score, d_score)

            print_results(i, s_score, s_time, s_resp, d_score, d_time, d_resp, kws, better, improvement)

            subj_results.append({
                "question": q,
                "keywords": kws,
                "expected": item["expected"],
                "single_pass": {"response": s_resp[:300], "score": s_score, "time_s": s_time},
                "deep_reason": {"response": d_resp[:300], "score": d_score, "time_s": d_time},
                "improvement_pct": improvement,
            })

            update_totals(totals["single"], s_score, s_time)
            update_totals(totals["deep"], d_score, d_time)

        all_results[subj] = subj_results

    summary = generate_summary(all_results, totals)
    print_final_summary(summary)
    save_results(summary)

    return summary

def print_header(subject: str, question_count: int):
    print(f"\n{'═'*60}")
    print(f"  📋 Subject: {subject.upper()}  ({question_count} questions)")
    print(f"{'═'*60}")

def print_question(index: int, question: str):
    q = question[:80] + ('...' if len(question) > 80 else '')
    print(f"\n  Q{index}: {q}")

def calculate_improvement(s_score: float, d_score: float) -> float:
    return round((d_score - s_score) * 100, 1)

def determine_better(s_score: float, d_score: float) -> str:
    if d_score > s_score:
        return "🟢 better"
    elif d_score < s_score:
        return "🔴 same/worse"
    else:
        return "🟡 equal"

def print_results(index: int, s_score: float, s_time: float, s_resp: str, d_score: float, d_time: float, d_resp: str, kws: list, better: str, improvement: float):
    print(f"  ┌─ Single-pass  score={s_score:.2f} | {s_time}s")
    print(f"  │  {s_resp[:120].strip()}")
    print(f"  ├─ Deep reason  score={d_score:.2f} | {d_time}s  {better}")
    print(f"  │  {d_resp[:120].strip()}")
    print(f"  └─ Keywords: {kws}")

def update_totals(total: dict, score: float, time: float):
    total["score"] += score
    total["time"] += time
    total["n"] += 1

def generate_summary(all_results: dict, totals: dict) -> dict:
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

    return {
        "model": MODEL,
        "date": datetime.now().isoformat(),
        "total_questions": n,
        "single_pass":  {"avg_score": avg_s, "avg_time_s": avg_t_s},
        "deep_reasoning": {"avg_score": avg_d, "avg_time_s": avg_t_d},
        "deep_wins": win,
        "overall_improvement_pct": round((avg_d - avg_s) * 100, 1),
        "results": all_results,
    }

def print_final_summary(summary: dict):
    print(f"\n{'═'*60}")
    print("  📊 FINAL SUMMARY")
    print(f"{'═'*60}")
    print(f"  Model         : {summary['model']}")
    print(f"  Questions     : {summary['total_questions']}")
    print(f"  Single-pass   : avg score={summary['single_pass']['avg_score']:.3f} | avg {summary['single_pass']['avg_time_s']}s/q")
    print(f"  Deep reasoning: avg score={summary['deep_reasoning']['avg_score']:.3f} | avg {summary['deep_reasoning']['avg_time_s']}s/q")
    print(f"  Deep wins     : {summary['deep_wins']}/{summary['total_questions']} questions")
    print(f"  Improvement   : {summary['overall_improvement_pct']:+.1f}%")
    print(f"{'═'*60}\n")

def save_results(summary: dict):
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"  💾 Results saved → {RESULTS_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark: single-pass vs deep reasoning")
    parser.add_argument("--subject", choices=["coding", "math", "punjabi"],
                        help="Test one subject only (default: all)")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.subject))