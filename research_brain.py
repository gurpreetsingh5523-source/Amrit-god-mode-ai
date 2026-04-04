"""
Research Brain — AMRIT GODMODE ਦਾ ਵਿਗਿਆਨਕ ਦਿਮਾਗ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scientific research pipeline:
  1. ਪਰੀਕਲਪਨਾ (Hypothesis Generation)
  2. ਅੰਤਰ-ਵਿਸ਼ਿਆਂ ਦਾ ਗਿਆਨ (Cross-Domain Learning)
  3. ਪ੍ਰਯੋਗ ਡਿਜ਼ਾਈਨ (Experiment Design)
  4. ਨਤੀਜੇ ਪ੍ਰਮਾਣਿਤ (Validation)
  5. ਖੋਜ ਰਿਪੋਰਟ (Research Report)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json
import time
from pathlib import Path
from datetime import datetime
from logger import setup_logger

logger = setup_logger("ResearchBrain")

# ── Scientific Domains for Cross-Domain Learning ──────────────
DOMAINS = {
    "physics":    ["quantum mechanics", "thermodynamics", "electromagnetism", "relativity", "optics"],
    "biology":    ["genetics", "evolution", "neuroscience", "ecology", "cell biology"],
    "chemistry":  ["organic", "inorganic", "biochemistry", "catalysis", "polymer"],
    "math":       ["topology", "statistics", "graph theory", "calculus", "number theory"],
    "cs":         ["algorithms", "machine learning", "distributed systems", "cryptography", "NLP"],
    "medicine":   ["pharmacology", "immunology", "cardiology", "oncology", "epidemiology"],
    "engineering":["materials science", "robotics", "signal processing", "control theory", "fluid dynamics"],
    "psychology": ["cognitive science", "behavioral", "developmental", "social", "neuropsychology"],
}

# ── Cross-Domain Bridges (known connections) ──────────────────
CROSS_BRIDGES = [
    ("physics.thermodynamics",  "biology.ecology",        "energy flow in ecosystems follows thermodynamic laws"),
    ("physics.quantum mechanics","chemistry.catalysis",    "quantum tunneling affects chemical reaction rates"),
    ("math.graph theory",       "biology.genetics",        "gene regulatory networks modeled as directed graphs"),
    ("math.statistics",         "medicine.epidemiology",   "Bayesian inference for disease outbreak modeling"),
    ("cs.machine learning",     "biology.neuroscience",    "neural networks inspired by biological neurons"),
    ("cs.algorithms",           "biology.evolution",       "genetic algorithms mirror natural selection"),
    ("physics.optics",          "medicine.oncology",       "photodynamic therapy uses light-matter interaction"),
    ("engineering.materials science", "medicine.pharmacology", "drug delivery via nanoparticles"),
    ("psychology.cognitive science",  "cs.NLP",            "language models reflect human language processing"),
    ("math.topology",           "physics.quantum mechanics","topological quantum computing"),
    ("chemistry.biochemistry",  "cs.algorithms",           "protein folding as optimization problem"),
    ("engineering.robotics",    "biology.neuroscience",     "brain-computer interfaces"),
]

RESEARCH_DIR = Path("workspace/research")


class ResearchBrain:
    """
    Scientific thinking engine.
    - Generates hypotheses from observations
    - Finds cross-domain connections
    - Designs experiments
    - Validates results
    - Produces research reports
    """

    def __init__(self, orchestrator):
        self.orc = orchestrator
        self._hypotheses = []
        self._findings = []
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════
    # 1. HYPOTHESIS GENERATION — ਪਰੀਕਲਪਨਾ ਬਣਾਉਣਾ
    # ══════════════════════════════════════════════════════════════

    async def generate_hypotheses(self, observation: str, domain: str = "",
                                   num: int = 3) -> list:
        """
        Given an observation, generate testable hypotheses.
        "ਜੇ ਅਸੀਂ ਇਸ ਨੂੰ ਇੰਝ ਕਰੀਏ ਤਾਂ ਕੀ ਹੋਵੇਗਾ?"
        """
        logger.info(f"Generating hypotheses for: {observation[:80]}")

        # Find cross-domain insights
        cross_insights = self._find_cross_connections(domain) if domain else ""

        domain_line = f"DOMAIN: {domain}" if domain else ""
        cross_line = f"CROSS-DOMAIN INSIGHTS:\n{cross_insights}" if cross_insights else ""

        prompt = f"""You are a scientific research AI. Given this observation, generate {num} testable hypotheses.

OBSERVATION: {observation}
{domain_line}
{cross_line}

For EACH hypothesis provide:
1. HYPOTHESIS: Clear, testable statement (If X, then Y)
2. MECHANISM: Why this would work (underlying science)
3. TEST: How to verify this (specific experiment)
4. PREDICTION: Expected measurable outcome
5. CONFIDENCE: Low/Medium/High based on existing evidence

Return as JSON array:
[{{"hypothesis": "...", "mechanism": "...", "test": "...", "prediction": "...", "confidence": "..."}}]"""

        router = await self._get_router()
        raw = await router.complete(prompt, max_tokens=2000)

        hypotheses = self._parse_json_list(raw)
        if not hypotheses:
            hypotheses = [{"hypothesis": raw, "mechanism": "", "test": "",
                           "prediction": "", "confidence": "unknown"}]

        # Store
        entry = {
            "observation": observation,
            "domain": domain,
            "hypotheses": hypotheses,
            "timestamp": datetime.now().isoformat()
        }
        self._hypotheses.append(entry)
        self._save_research("hypotheses", entry)

        logger.info(f"Generated {len(hypotheses)} hypotheses")
        return hypotheses

    # ══════════════════════════════════════════════════════════════
    # 2. CROSS-DOMAIN LEARNING — ਅੰਤਰ-ਵਿਸ਼ਿਆਂ ਦਾ ਗਿਆਨ
    # ══════════════════════════════════════════════════════════════

    async def cross_domain_analysis(self, topic: str, source_domain: str,
                                      target_domain: str) -> dict:
        """
        Apply principles from one domain to another.
        e.g., Physics → Biology, Math → Medicine
        """
        logger.info(f"Cross-domain: {source_domain} → {target_domain} for '{topic}'")

        # Find known bridges
        bridges = [b for b in CROSS_BRIDGES
                   if source_domain.lower() in b[0].lower() or
                   target_domain.lower() in b[1].lower()]
        bridge_text = "\n".join(f"- {b[0]} → {b[1]}: {b[2]}" for b in bridges)

        # Get source domain principles
        source_principles = DOMAINS.get(source_domain.lower(), [])
        target_areas = DOMAINS.get(target_domain.lower(), [])

        prompt = f"""Perform cross-domain scientific analysis:

TOPIC: {topic}
SOURCE DOMAIN: {source_domain} (areas: {', '.join(source_principles)})
TARGET DOMAIN: {target_domain} (areas: {', '.join(target_areas)})

KNOWN CROSS-DOMAIN BRIDGES:
{bridge_text if bridge_text else 'None known — discover new connections!'}

Analyze:
1. TRANSFER: Which principles from {source_domain} can apply to {target_domain}?
2. ANALOGY: What structural similarities exist between the domains?
3. NOVEL_INSIGHT: What new research direction does this cross-domain view suggest?
4. HYPOTHESIS: State one testable hypothesis from this cross-domain analysis.
5. RISK: What are the limits of this cross-domain application?

Return detailed analysis."""

        router = await self._get_router()
        analysis = await router.complete(prompt, max_tokens=2000)

        result = {
            "topic": topic,
            "source": source_domain,
            "target": target_domain,
            "bridges_found": len(bridges),
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
        self._save_research("cross_domain", result)

        return result

    def _find_cross_connections(self, domain: str) -> str:
        """Find all known cross-domain connections for a domain."""
        connections = []
        for src, tgt, desc in CROSS_BRIDGES:
            if domain.lower() in src.lower() or domain.lower() in tgt.lower():
                connections.append(f"  {src} ↔ {tgt}: {desc}")
        return "\n".join(connections) if connections else ""

    # ══════════════════════════════════════════════════════════════
    # 3. FULL RESEARCH PIPELINE — ਪੂਰੀ ਖੋਜ ਪਾਈਪਲਾਈਨ
    # ══════════════════════════════════════════════════════════════

    async def full_research(self, question: str, domain: str = "") -> dict:
        """
        Full scientific research cycle:
        1. Search existing literature (Internet Agent)
        2. Generate hypotheses
        3. Design experiment (Simulation Agent)
        4. Validate with simulation
        5. Produce research report
        """
        logger.info(f"\n{'═' * 50}")
        logger.info(f"  🔬 FULL RESEARCH: {question[:60]}")
        logger.info(f"{'═' * 50}")

        t0 = time.time()
        report = {"question": question, "domain": domain, "steps": {}}

        # Step 1: Literature search
        logger.info("📚 Step 1: Literature search...")
        internet = self.orc.get_agent("internet")
        lit_review = {}
        if internet:
            lit_review = await internet.execute({
                "name": f"Literature: {question[:40]}",
                "data": {"action": "search",
                         "query": f"scientific research {domain} {question} latest findings"}
            })
            report["steps"]["literature"] = {
                "results": len(lit_review.get("results", [])),
                "summary": str(lit_review.get("answer", ""))[:500]
            }

        # Step 2: arXiv search (via internet agent)
        logger.info("📄 Step 2: arXiv search...")
        if internet:
            arxiv_results = await internet.execute({
                "name": f"arXiv: {question[:40]}",
                "data": {"action": "arxiv", "query": question, "max_results": 5}
            })
            report["steps"]["arxiv"] = arxiv_results.get("papers", [])[:3]

        # Step 3: Generate hypotheses
        logger.info("💡 Step 3: Hypothesis generation...")
        context = str(lit_review.get("answer", ""))[:500]
        hypotheses = await self.generate_hypotheses(
            f"{question}\nExisting knowledge: {context}", domain
        )
        report["steps"]["hypotheses"] = hypotheses

        # Step 4: Simulation / Experiment design
        logger.info("🧪 Step 4: Experiment design...")
        sim = self.orc.get_agent("simulation")
        if sim and hypotheses:
            best_h = hypotheses[0]
            experiment = await sim.execute({
                "name": f"Test: {best_h.get('hypothesis', '')[:50]}",
                "data": {
                    "action": "experiment",
                    "name": question[:40],
                    "description": f"Test hypothesis: {best_h.get('hypothesis', '')}\n"
                                   f"Method: {best_h.get('test', '')}\n"
                                   f"Prediction: {best_h.get('prediction', '')}"
                }
            })
            report["steps"]["experiment"] = {
                "design": str(experiment.get("design", ""))[:500]
            }

        # Step 5: Validate
        logger.info("✅ Step 5: Validation...")
        if sim and hypotheses:
            validation = await sim.execute({
                "name": f"Validate: {question[:40]}",
                "data": {
                    "action": "hypothesis",
                    "hypothesis": hypotheses[0].get("hypothesis", question)
                }
            })
            report["steps"]["validation"] = {
                "evaluation": str(validation.get("evaluation", ""))[:500]
            }

        # Step 6: Generate report
        logger.info("📝 Step 6: Research report...")
        elapsed = time.time() - t0
        report["elapsed_seconds"] = round(elapsed, 1)
        report["timestamp"] = datetime.now().isoformat()

        # Write full report
        await self._write_report(question, report)

        logger.info(f"🔬 Research complete in {elapsed:.1f}s")
        return report

    # ══════════════════════════════════════════════════════════════
    # PAPER ANALYSIS — ਪੇਪਰ ਵਿਸ਼ਲੇਸ਼ਣ
    # ══════════════════════════════════════════════════════════════

    async def analyze_paper(self, paper_text: str, focus: str = "") -> dict:
        """Analyze a research paper and extract key insights."""
        router = await self._get_router()
        prompt = f"""Analyze this research paper{' focusing on ' + focus if focus else ''}:

{paper_text[:3000]}

Extract:
1. MAIN_FINDING: Core discovery in one sentence
2. METHOD: Research methodology used
3. KEY_DATA: Important numerical results
4. LIMITATIONS: What the study didn't address
5. FUTURE_WORK: What research should follow
6. CROSS_DOMAIN: How can this apply to other fields?
7. HYPOTHESIS: What new hypothesis does this suggest?"""

        analysis = await router.complete(prompt, max_tokens=1500)
        return {
            "focus": focus,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }

    # ══════════════════════════════════════════════════════════════
    # UTILITIES
    # ══════════════════════════════════════════════════════════════

    async def _get_router(self):
        from llm_router import LLMRouter
        return LLMRouter()

    def _parse_json_list(self, text: str) -> list:
        import re
        clean = re.sub(r"```(?:json)?|```", "", text).strip()
        match = re.search(r'\[.*\]', clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return []

    def _save_research(self, category: str, data: dict):
        f = RESEARCH_DIR / f"{category}.jsonl"
        with open(f, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(data, default=str) + "\n")

    async def _write_report(self, title: str, report: dict):
        """Generate a readable markdown research report."""
        router = await self._get_router()

        report_prompt = f"""Write a scientific research report in markdown format.

QUESTION: {title}
DOMAIN: {report.get('domain', 'general')}

LITERATURE: {json.dumps(report['steps'].get('literature', {}), default=str)[:500]}
HYPOTHESES: {json.dumps(report['steps'].get('hypotheses', []), default=str)[:500]}
EXPERIMENT: {json.dumps(report['steps'].get('experiment', {}), default=str)[:300]}
VALIDATION: {json.dumps(report['steps'].get('validation', {}), default=str)[:300]}

Write a clear, structured report with:
- Abstract
- Introduction
- Hypotheses
- Methodology
- Expected Results
- Conclusion
- Future Work"""

        md = await router.complete(report_prompt, max_tokens=2000)

        # Save report
        safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:40].strip()
        path = RESEARCH_DIR / f"report_{safe_name}.md"
        path.write_text(f"# Research Report: {title}\n\n"
                        f"*Generated: {report.get('timestamp', '')}*\n"
                        f"*Time: {report.get('elapsed_seconds', 0)}s*\n\n"
                        f"{md}\n")
        logger.info(f"📝 Report saved: {path}")
