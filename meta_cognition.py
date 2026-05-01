class MetaCognition:
    def analyze_self(self, logs, performance, llm_fail_rate=None):
        insights = []

        if performance.get("fail_rate", 0) > 0.2:
            insights.append("Too many failures → improve planning")

        if performance.get("latency", 0) > 40:
            insights.append("Slow thinking → optimize model usage")

        # LLM fail rate insight
        if llm_fail_rate is not None and llm_fail_rate > 0.3:
            insights.append("llm_unstable")

        return insights

    def decide_strategy(self, insights):
        if any("Too many failures" in str(i) for i in insights):
            return "increase_testing"
        return "normal"
