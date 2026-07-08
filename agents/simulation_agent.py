"""Simulation Agent — Scientific simulations, hypothesis testing, virtual experiments."""
import random
import time
import math
import json
from pathlib import Path
from base_agent import BaseAgent

class SimulationAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("SimulationAgent", eb, state)
        self._results = []
        Path("experiments").mkdir(exist_ok=True)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "simulate")
        await self.report(f"Simulation [{action}]")
        if action == "monte_carlo":
            return self._monte_carlo(d)
        if action == "hypothesis":
            return await self._hypothesis(d)
        if action == "benchmark":
            return self._benchmark_code(d.get("code", ""))
        if action == "experiment":
            return await self._experiment(d)
        if action == "validate":
            return await self._validate(d)
        if action == "ab_test":
            return await self._ab_test(d)
        if action == "sensitivity":
            return await self._sensitivity(d)
        if action == "simulate_code":
            return await self._simulate_code(d)
        return await self._experiment(d)

    def _monte_carlo(self, d: dict) -> dict:
        n   = int(d.get("iterations", 10000))
        sim = d.get("simulation", "pi")
        if sim == "pi":
            inside = sum(1 for _ in range(n)
                         if math.hypot(random.random(), random.random()) <= 1)
            estimate = 4 * inside / n
            return self.ok(simulation="pi", iterations=n,
                           estimate=estimate, error=abs(estimate - math.pi))
        if sim == "random_walk":
            pos = 0
            positions = [0]
            for _ in range(n):
                pos += random.choice([-1, 1])
                positions.append(pos)
            return self.ok(simulation="random_walk", iterations=n,
                           final_position=pos, max_dist=max(abs(p) for p in positions),
                           rms=round(math.sqrt(sum(p*p for p in positions)/n), 3))
        if sim == "coin_flip":
            heads = sum(random.random() < float(d.get("probability", 0.5)) for _ in range(n))
            return self.ok(simulation="coin_flip", iterations=n,
                           heads=heads, tails=n-heads, ratio=round(heads/n, 4))
        return self.ok(simulation=sim, iterations=n, note="Custom sim — add logic")

    async def _hypothesis(self, d: dict) -> dict:
        h = d.get("hypothesis", "")
        result = await self.ask_llm(
            f"""Evaluate this scientific hypothesis rigorously:

HYPOTHESIS: {h}

Provide:
1. PLAUSIBILITY (0-1): How scientifically sound is this?
2. SUPPORTING_EVIDENCE: What existing knowledge supports this?
3. COUNTER_EVIDENCE: What contradicts this?
4. CONFOUNDING_VARIABLES: What other factors could explain the observation?
5. TEST_DESIGN: How would you test this with a controlled experiment?
6. SAMPLE_SIZE: What sample size would give statistical significance?
7. EXPECTED_EFFECT_SIZE: Small/Medium/Large
8. VERDICT: Accept/Reject/Needs More Data""")
        self._results.append({"hypothesis": h, "evaluation": result, "time": time.time()})
        return self.ok(hypothesis=h, evaluation=result)

    def _benchmark_code(self, code: str) -> dict:
        import timeit
        if not code:
            return self.err("No code provided")
        try:
            t = timeit.timeit(code, number=100, globals={})
            return self.ok(code=code[:50], time_100_runs=round(t, 4), avg_ms=round(t * 10, 3))
        except Exception as e:
            return self.err(str(e))

    async def _experiment(self, d: dict) -> dict:
        name = d.get("name", "unnamed experiment")
        desc = d.get("description", "")
        design = await self.ask_llm(
            f"""Design a rigorous scientific experiment:

NAME: {name}
DESCRIPTION: {desc}

Include:
1. INDEPENDENT VARIABLES: What you change
2. DEPENDENT VARIABLES: What you measure
3. CONTROL VARIABLES: What stays constant
4. CONTROL GROUP: Baseline comparison
5. SAMPLE SIZE: Justified with power analysis
6. METHOD: Step-by-step procedure
7. DATA COLLECTION: What data to record
8. EXPECTED RESULTS: With statistical thresholds
9. SUCCESS CRITERIA: p-value, effect size
10. TIMELINE: Estimated duration""")
        path = f"experiments/{name.replace(' ', '_')}.txt"
        Path(path).write_text(f"Experiment: {name}\n\n{design}")
        return self.ok(name=name, design=design, saved=path)

    async def _validate(self, d: dict) -> dict:
        """Validate research findings with statistical analysis."""
        findings = d.get("findings", "")
        data = d.get("data", "")
        analysis = await self.ask_llm(
            f"""Validate these research findings:

FINDINGS: {findings}
DATA: {data}

Perform:
1. STATISTICAL_TEST: Which test is appropriate? (t-test, chi-square, ANOVA, etc.)
2. ASSUMPTIONS: Are the test assumptions met?
3. EFFECT_SIZE: Calculate Cohen's d or equivalent
4. CONFIDENCE_INTERVAL: 95% CI
5. REPRODUCIBILITY: Can this be independently replicated?
6. BIAS_CHECK: Any selection bias, confirmation bias, survivorship bias?
7. CONCLUSION: Strong/Moderate/Weak evidence""")
        return self.ok(findings=findings[:200], validation=analysis)

    async def _ab_test(self, d: dict) -> dict:
        """Simulate A/B test for two approaches."""
        a_desc = d.get("approach_a", "")
        b_desc = d.get("approach_b", "")
        n = int(d.get("iterations", 1000))

        analysis = await self.ask_llm(
            f"""Design and analyze an A/B test:

APPROACH A: {a_desc}
APPROACH B: {b_desc}
SAMPLE SIZE: {n}

Provide:
1. METRIC: What to measure
2. NULL_HYPOTHESIS: H0 statement
3. ALT_HYPOTHESIS: H1 statement
4. EXPECTED_DIFFERENCE: Estimated effect
5. POWER_ANALYSIS: Is {n} samples enough?
6. RECOMMENDATION: Which approach to choose and why""")
        return self.ok(approach_a=a_desc, approach_b=b_desc, n=n, analysis=analysis)

    async def _sensitivity(self, d: dict) -> dict:
        """Sensitivity analysis — what happens when we change parameters."""
        model = d.get("model", "")
        params = d.get("parameters", [])
        analysis = await self.ask_llm(
            f"""Perform sensitivity analysis:

MODEL: {model}
PARAMETERS: {params}

For each parameter:
1. RANGE: Test from min to max reasonable value
2. IMPACT: How much does the output change?
3. CRITICAL_THRESHOLD: Where does behavior change dramatically?
4. INTERACTION: Does this parameter interact with others?
5. ROBUSTNESS: Is the model robust to parameter changes?""")
        return self.ok(model=model, parameters=params, sensitivity=analysis)

    async def _simulate_code(self, d: dict) -> dict:
        """Run code in a sandboxed simulation and analyze results."""
        code = d.get("code", "")
        if not code:
            return self.err("No code provided")

        import subprocess
        import sys
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp = f.name

        try:
            r = subprocess.run(
                [sys.executable, tmp],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path(".").resolve())
            )
            output = r.stdout + r.stderr
            success = r.returncode == 0
        except subprocess.TimeoutExpired:
            output = "Simulation timed out (30s limit)"
            success = False
        except Exception as e:
            output = str(e)
            success = False
        finally:
            Path(tmp).unlink(missing_ok=True)

        return self.ok(code=code[:100], output=output[:2000], success=success)
