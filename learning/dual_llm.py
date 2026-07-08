"""
dual_llm.py — two different LLMs answer in PARALLEL, a third analyses & picks best
═══════════════════════════════════════════════════════════════════════════════
The idea (user's): one model answers, another is the best analyser and uses it —
two different LLMs at the same time. This is the proven "ensemble + judge" pattern:
diversity (two distinct models) + a critic = more reliable than any single model.

  Generator A : Amrit's fine-tuned coder  (model="amrit-coder")   ─┐  run in
  Generator B : DeepSeek                   (model=default)         ─┤  PARALLEL
  Analyser C  : DeepSeek-Reasoner — compares A & B, picks/merges the best ─┘

    from dual_llm import dual_answer
    print(await dual_answer("write a function to merge two sorted lists"))
"""
import asyncio
import re
from logger import setup_logger

logger = setup_logger("DualLLM")


def _strip(t):
    return re.sub(r"^```[a-z]*\n|```$", "", (t or "").strip(), flags=re.M).strip()


async def dual_answer(task: str, is_code: bool = True) -> dict:
    """Two different LLMs answer in parallel; an analyser picks/merges the best."""
    from llm_router import LLMRouter
    router = LLMRouter()

    # ── 1) two DIFFERENT models answer AT THE SAME TIME ──
    gen = (task + ("\nReturn only the code in one ```python block." if is_code else ""))
    a, b = await asyncio.gather(
        router.complete(gen, model="amrit-coder", max_tokens=500),   # Amrit's own brain
        router.complete(gen, max_tokens=500),                         # DeepSeek (different LLM)
        return_exceptions=True,
    )
    a = _strip(a) if isinstance(a, str) else ""
    b = _strip(b) if isinstance(b, str) else ""

    # ── 2) analyser (a third, reasoning model) judges & returns the best ──
    analyze = (
        f"Task: {task}\n\nTwo different AI models produced these answers.\n\n"
        f"=== Answer A (Amrit fine-tuned) ===\n{a or '(none)'}\n\n"
        f"=== Answer B (DeepSeek) ===\n{b or '(none)'}\n\n"
        "Analyse both for correctness (especially edge cases). Return the BEST, "
        "fully-correct version (merge their strengths or fix bugs). For code, return "
        "ONLY one ```python block. Start your reply with 'WINNER: A' or 'WINNER: B' "
        "or 'WINNER: merged'."
    )
    verdict = await router.complete(analyze, model="reasoning", max_tokens=700)
    winner = "merged"
    m = re.search(r"WINNER:\s*(A|B|merged)", verdict or "", re.I)
    if m:
        winner = m.group(1)
    best = _strip(re.sub(r"WINNER:\s*(A|B|merged)\s*", "", verdict or "", flags=re.I))

    # ── 3) verify the chosen code runs ──
    verified = None
    if is_code:
        try:
            exec(best, {}); verified = True
        except Exception:
            verified = False

    return {"winner": winner, "answer_a": a, "answer_b": b, "best": best, "verified": verified}


if __name__ == "__main__":
    async def _t():
        r = await dual_answer("Write a Python function fib(n) returning the n-th Fibonacci number (fib(0)=0).")
        print("WINNER:", r["winner"], "| verified:", r["verified"])
        print("─" * 50)
        print(r["best"][:400])
    asyncio.run(_t())
