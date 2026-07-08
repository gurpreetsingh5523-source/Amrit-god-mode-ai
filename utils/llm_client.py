"""
llm_client.py — LLMClient shim for DualBrain v3 compatibility.
Wraps Amrit's LLMRouter so DualBrain agents can call it synchronously.
"""
import asyncio
from dataclasses import dataclass


@dataclass
class _Response:
    output: str


class LLMClient:
    """Synchronous LLM wrapper used by DualBrain agent_builder."""

    def __init__(self, system_prompt: str = "", model: str = None):
        self.system_prompt = system_prompt
        self.model = model

    def _run(self, coro):
        """Run async coroutine synchronously (works inside or outside event loop)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    fut = pool.submit(asyncio.run, coro)
                    return fut.result(timeout=120)
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def complete(self, prompt: str, max_tokens: int = 2000) -> str:
        """Synchronous LLM call via Amrit's LLMRouter."""
        async def _call():
            from llm_router import LLMRouter
            router = LLMRouter()
            return await router.complete(
                prompt=prompt,
                system=self.system_prompt or None,
                model=self.model,
                max_tokens=max_tokens
            )
        try:
            return self._run(_call())
        except Exception as e:
            return f"[LLMClient error: {e}]"

    def execute(self, prompt: str) -> _Response:
        """DualBrain agent interface — returns object with .output attribute."""
        return _Response(output=self.complete(prompt))

    def ask(self, prompt: str, max_tokens: int = 2000) -> str:
        """QuantumBrain interface (FailureDNA/SelfGraph/DreamEngine) — returns text."""
        return self.complete(prompt, max_tokens=max_tokens)
