"""
☬ AMRIT DEEP REASONER
OpenMythos RDT ਦਾ concept software-level ਤੇ implement ਕੀਤਾ।
ਕੋਈ GPU ਨਹੀਂ ਚਾਹੀਦਾ — Ollama ਵਰਤਦਾ ਹੈ।
"""

import time  # noqa: F401
from logger import setup_logger

logger = setup_logger("AmritDeepReasoner")


class AmritDeepReasoner:
    """
    OpenMythos ਤੋਂ ਪ੍ਰੇਰਿਤ Loop-based Reasoning।

    ਆਸਾਨ ਸਵਾਲ → 1-2 loops
    ਔਖਾ ਸਵਾਲ (Physics/Science) → 4-8 loops
    ਬਹੁਤ ਔਖਾ → 12+ loops
    """

    def __init__(self, llm_router):
        self.llm = llm_router
        self.max_loops = 8
        self.halt_threshold = 0.92  # ACT Halting concept
        
    def classify_depth(self, question: str) -> int:
        """ਸਵਾਲ ਦੀ ਗਹਿਰਾਈ ਨਾਪੋ"""
        deep_keywords = [
            'physics', 'quantum', 'universe', 'ਭੌਤਿਕੀ',
            'why', 'ਕਿਉਂ', 'explain', 'ਸਮਝਾਓ',
            'science', 'ਵਿਗਿਆਨ', 'math', 'ਗਣਿਤ',
            'solve', 'ਹੱਲ', 'complex', 'ਔਖਾ'
        ]

        q_lower = question.lower()
        depth_score = sum(1 for kw in deep_keywords if kw in q_lower)

        if depth_score == 0:
            return 1   # Simple → 1 loop
        elif depth_score <= 2:
            return 3   # Medium → 3 loops
        elif depth_score <= 4:
            return 6   # Hard → 6 loops
        else:
            return 10  # Very Hard → 10 loops

    async def reason(self, question: str, context: str = "") -> dict:
        """
        Loop-based ਸੋਚ — OpenMythos RDT ਦਾ software version.
        LLMRouter.complete() (async) ਵਰਤਦਾ ਹੈ।
        """
        n_loops = min(self.classify_depth(question), self.max_loops)
        thoughts = []
        current_answer = ""
        confidence = 0.0
        loop_i = 1

        logger.info(f"☬ Deep Reasoning: {n_loops} loops ਸ਼ੁਰੂ...")

        for loop_i in range(1, n_loops + 1):
            # ਹਰ loop ਪਿਛਲੇ ਸੋਚ ਤੋਂ ਅੱਗੇ ਵਧਦਾ ਹੈ
            if loop_i == 1:
                prompt = (
                    f"ਸਵਾਲ: {question}\n"
                    + (f"\nਸੰਦਰਭ: {context}\n" if context else "")
                    + "\nਪਹਿਲੀ ਸੋਚ: ਇਸ ਸਵਾਲ ਦੀ ਪਹਿਲੀ ਸਮਝ ਦੱਸੋ।\nਕੀ ਕੁਝ ਅਧੂਰਾ ਰਹਿੰਦਾ ਹੈ?"
                )
            elif loop_i < n_loops:
                prompt = (
                    f"ਸਵਾਲ: {question}\n\n"
                    f"ਪਿਛਲੀ ਸੋਚ (Loop {loop_i - 1}):\n{current_answer}\n\n"
                    f"Loop {loop_i}: ਉੱਪਰਲੀ ਸੋਚ ਵਿੱਚ ਕੀ ਕਮੀ ਹੈ?\n"
                    "ਹੋਰ ਡੂੰਘੇ ਜਾਓ। ਕੋਈ ਨਵਾਂ ਪਹਿਲੂ?"
                )
            else:
                thought_summary = "\n".join(
                    f"Loop {i + 1}: {t[:100]}..." for i, t in enumerate(thoughts)
                )
                prompt = (
                    f"ਸਵਾਲ: {question}\n\n"
                    f"ਸਾਰੀ ਸੋਚ-ਪ੍ਰਕਿਰਿਆ:\n{thought_summary}\n\n"
                    "ਅੰਤਿਮ ਜਵਾਬ: ਸਭ ਸੋਚਾਂ ਨੂੰ ਜੋੜ ਕੇ ਮੁਕੰਮਲ ਅਤੇ ਸਹੀ ਜਵਾਬ ਦਿਓ।"
                )

            # async LLMRouter.complete() — generate() ਨਹੀਂ
            response = await self.llm.complete(
                prompt,
                system="ਤੁਸੀਂ AMRIT ਹੋ — ਡੂੰਘੀ ਸੋਚ ਨਾਲ ਜਵਾਬ ਦਿਓ।",
                max_tokens=600,
            )
            thoughts.append(response)
            current_answer = response

            # ACT Halting — ਜੇ ਜਵਾਬ ਕਾਫ਼ੀ ਚੰਗਾ ਹੈ, ਰੁਕੋ
            confidence = self._estimate_confidence(response)
            if confidence > self.halt_threshold and loop_i >= 2:
                logger.info(f"  ✅ Loop {loop_i} ਤੇ ਰੁਕਿਆ (confidence: {confidence:.2f})")
                break

            logger.info(f"  🔄 Loop {loop_i}/{n_loops} ਮੁਕੰਮਲ")

        return {
            "question": question,
            "answer": current_answer,
            "loops_used": loop_i,
            "loops_planned": n_loops,
            "thoughts": thoughts,
            "confidence": confidence,
        }
    
    def _estimate_confidence(self, response: str) -> float:
        """ਜਵਾਬ ਦੀ ਭਰੋਸੇਯੋਗਤਾ ਮਾਪੋ"""
        # ਸਾਦਾ heuristic — ਅਸਲ ACT ਇੱਕ neural layer ਵਰਤਦਾ ਹੈ
        uncertainty_words = [
            'maybe', 'perhaps', 'ਸ਼ਾਇਦ', 'unclear', 'ਅਸਪੱਸ਼ਟ',
            'not sure', 'ਪੱਕਾ ਨਹੀਂ', 'might', 'ਹੋ ਸਕਦਾ'
        ]
        count = sum(1 for w in uncertainty_words if w in response.lower())
        return max(0.5, 1.0 - (count * 0.1))
