"""Goal Parser — NL goal to structured task list via LLM + rules."""
import re, json
from logger import setup_logger
logger = setup_logger("GoalParser")

PATTERNS = [
    # Research / Search
    (r"(research|find|search|look up|ਲੱਭੋ|ਖੋਜ)\s+(.+)",
     lambda m:[{"name":f"Internet search: {m.group(2)}","agent":"internet","priority":1,"data":{"action":"search","query":m.group(2)}}]),
    # Scientific Research — hypothesis, experiment, arxiv, pubmed
    (r"(?:hypothesis|hypothesize|experiment|simulate|ਪਰੀਕਲਪਨਾ|ਪ੍ਰਯੋਗ)\s+(.+)",
     lambda m:[{"name":f"Research: {m.group(1)}","agent":"researcher","priority":1,
               "data":{"action":"analyze","query":m.group(1)}},
              {"name":f"Simulate: {m.group(1)}","agent":"simulation","priority":2,
               "data":{"action":"hypothesis","hypothesis":m.group(1)}}]),
    # arXiv / Paper search
    (r"(?:arxiv|paper|papers|ਪੇਪਰ)\s+(?:on\s+|about\s+|for\s+)?(.+)",
     lambda m:[{"name":f"arXiv: {m.group(1)}","agent":"internet","priority":1,
               "data":{"action":"arxiv","query":m.group(1),"max_results":5}}]),
    # PubMed / Medical research
    (r"(?:pubmed|medical|biomedical|ਮੈਡੀਕਲ)\s+(?:research\s+)?(.+)",
     lambda m:[{"name":f"PubMed: {m.group(1)}","agent":"internet","priority":1,
               "data":{"action":"pubmed","query":m.group(1),"max_results":5}}]),
    # Deep Thinking / Reasoning
    (r"(?:think|reason|analyze deeply|ਸੋਚ|ਡੂੰਘੀ ਸੋਚ)\s+(?:about\s+)?(.+)",
     lambda m:[{"name":f"Deep Think: {m.group(1)}","agent":"researcher","priority":1,
               "data":{"action":"analyze","query":m.group(1),"deep":True}}]),
    # Optimize code
    (r"(?:optimize|ਅਨੁਕੂਲ|speed up|make faster|memory)\s+(.+)",
     lambda m:[{"name":f"Optimize: {m.group(1)}","agent":"debugger","priority":1,
               "data":{"action":"optimize","file":m.group(1)}}]),
    # Creative — poem, story, song, essay (MUST come BEFORE build/code pattern)
    (r"(?:make|write|create|generate|ਲਿਖੋ|ਬਣਾਓ)\s+(?:a\s+|an\s+)?(?:punjabi\s+|ਪੰਜਾਬੀ\s+)?(poem|story|song|essay|shayari|ਕਵਿਤਾ|ਗੀਤ|ਕਹਾਣੀ|ਲੇਖ|ਸ਼ਾਇਰੀ|lyrics|letter|joke|ਚਿੱਠੀ|ਚੁਟਕਲਾ)(.*)$",
     lambda m:[{"name":f"Write {m.group(1)}{m.group(2)}","agent":"coder","priority":1,
               "data":{"action":"generate","spec":f"Write a beautiful Punjabi {m.group(1)} in Gurmukhi script{m.group(2)}. Be creative and emotional.","language":"text"}}]),
    # Build / Create / Code (non-creative)
    (r"(write|create|build|code|generate|ਬਣਾਓ|ਲਿਖੋ)\s+(.+)",
     lambda m:[{"name":f"Plan: {m.group(2)}","agent":"planner","priority":1,"data":{"goal":m.group(2)}},
               {"name":f"Code: {m.group(2)}","agent":"coder","priority":2,"data":{"spec":m.group(2)}},
               {"name":f"Test: {m.group(2)}","agent":"tester","priority":3}]),
    # Debug / Fix
    (r"(debug|fix|troubleshoot|ਠੀਕ|ਸੁਧਾਰ)\s+(.+)",
     lambda m:[{"name":f"Debug: {m.group(2)}","agent":"debugger","priority":1,"data":{"action":"analyze","error":m.group(2)}}]),
    # Explain / Analyze
    (r"(explain|analyze|review|ਸਮਝਾਓ|ਵਿਸ਼ਲੇਸ਼ਣ)\s+(.+)",
     lambda m:[{"name":f"Analyze: {m.group(2)}","agent":"researcher","priority":1,"data":{"query":m.group(2)}},
               {"name":f"Report: {m.group(2)}","agent":"planner","priority":2,"data":{"goal":f"analyze {m.group(2)}"}}]),
    # Download / Fetch
    (r"(download|fetch|get|ਡਾਊਨਲੋਡ)\s+(.+)",
     lambda m:[{"name":f"Download: {m.group(2)}","agent":"internet","priority":1,"data":{"action":"download","url":m.group(2)}}]),
    # Test / Verify
    (r"(test|verify|check|ਟੈਸਟ|ਜਾਂਚ)\s+(.+)",
     lambda m:[{"name":f"Test: {m.group(2)}","agent":"tester","priority":1,"data":{"spec":m.group(2)}}]),
    # Monitor / Watch
    (r"(monitor|watch|track|ਨਿਗਰਾਨੀ)\s+(.+)",
     lambda m:[{"name":f"Monitor: {m.group(2)}","agent":"monitor","priority":1,"data":{"action":"check"}}]),
]

class GoalParser:
    def __init__(self): self._use_llm = True

    async def parse(self, goal: str) -> list:
        logger.info(f"Parsing: {goal!r}")
        # RULES FIRST — instant, no LLM call needed
        tasks = self._rule_parse(goal)
        if tasks:
            logger.info(f"Rule-matched → {len(tasks)} task(s) (no LLM needed)")
            return tasks
        # Only use LLM for goals that don't match any rule
        if self._use_llm:
            try:
                tasks = await self._llm_parse(goal)
                return tasks if tasks else [self._default(goal)]
            except Exception as e:
                logger.warning(f"LLM failed: {e}")
                return [self._default(goal)]
        return [self._default(goal)]

    async def _llm_parse(self, goal: str) -> list:
        from llm_router import LLMRouter
        system = "ਤੁਸੀਂ AMRIT GODMODE v2.1 ਹੋ। Decompose goals into 1-3 tasks ONLY. Keep it minimal. Return ONLY JSON array, no markdown."
        prompt = (
            f"GOAL: {goal}\n"
            "Agents: planner,coder,researcher,tester,debugger,tool,memory,internet,dataset,monitor\n"
            "JSON: [{'name':'...','agent':'...','priority':1,'depends_on':[],'data':{}}]"
        )
        r = await LLMRouter().complete(prompt, system=system, max_tokens=1000)
        if not isinstance(r, str) or not r:
            logger.warning("LLMRouter returned empty/non-string response; falling back to rules")
            return []
        return self._parse_json(r)

    def _rule_parse(self, goal: str) -> list:
        n = goal.lower().strip()
        # For creative/social media requests, create max 3 tasks
        if any(w in n for w in ["instagram", "post", "viral", "hashtag", "hook", "caption", "social media",
                                "ਪੋਸਟ", "ਵਾਇਰਲ", "ਸੋਸ਼ਲ ਮੀਡੀਆ"]):
            return [
                {"name": "Draft Post Idea", "agent": "planner", "priority": 1, "data": {"goal": goal}},
                {"name": "Generate Post Content", "agent": "coder", "priority": 2, "data": {"spec": goal}},
                {"name": "Research Hashtags", "agent": "researcher", "priority": 3, "data": {"query": "Punjabi trending hashtags"}}
            ]
        # YouTube / Video requests
        if any(w in n for w in ["youtube", "video", "ਵੀਡੀਓ", "ਯੂਟਿਊਬ"]):
            return [
                {"name": "Plan Video", "agent": "planner", "priority": 1, "data": {"goal": goal}},
                {"name": "Script Video", "agent": "coder", "priority": 2, "data": {"spec": goal}},
            ]
        # Stock / Finance requests
        if any(w in n for w in ["stock", "price", "market", "ਸ਼ੇਅਰ", "ਮਾਰਕੀਟ", "ਕੀਮਤ"]):
            return [
                {"name": "Fetch Market Data", "agent": "internet", "priority": 1, "data": {"action": "search", "query": goal}},
                {"name": "Analyze Data", "agent": "researcher", "priority": 2, "data": {"query": goal}},
            ]
        # Security / Antivirus requests
        if any(w in n for w in ["security", "scan", "virus", "malware", "ਸੁਰੱਖਿਆ"]):
            return [
                {"name": "Security Scan", "agent": "monitor", "priority": 1, "data": {"action": "check"}},
                {"name": "Report", "agent": "planner", "priority": 2, "data": {"goal": goal}},
            ]
        for pat, builder in PATTERNS:
            m = re.match(pat, n)
            if m: return builder(m)
        return []

    def _parse_json(self, text: str) -> list:
        import ast
        import re, json
        clean = re.sub(r"\`\`\`(?:json)?|\`\`\`", "", text).strip()
        # Strip any text before first [ and after last ]
        arr_match = re.search(r'\[.*\]', clean, re.DOTALL)
        if arr_match:
            clean = arr_match.group(0)
        candidates = []
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                candidates = parsed
            elif isinstance(parsed, dict) and isinstance(parsed.get("tasks"), list):
                candidates = parsed.get("tasks")
        except Exception:
            pass
        if not candidates:
            # 2) extract the first JSON array-looking substring (fallback)
            m = re.search(r"\[.*\]", clean, re.DOTALL)
            if m:
                snippet = m.group()
                try:
                    candidates = json.loads(snippet)
                except Exception:
                    # try to fix common single-quote usage and trailing commas
                    s = snippet
                    s = re.sub(r",\s*\]", "]", s)
                    s = s.replace("'", '"')
                    try:
                        candidates = json.loads(s)
                    except Exception:
                        try:
                            candidates = ast.literal_eval(snippet)
                        except Exception:
                            candidates = []

        if not candidates:
            logger.warning("Failed to parse JSON tasks from LLM output")
            return []

        out = []
        for t in candidates:
            if not isinstance(t, dict):
                continue
            # ensure required fields and sane types
            t.setdefault("priority", 5)
            t.setdefault("depends_on", [])
            try:
                t["priority"] = int(t.get("priority", 5))
            except Exception:
                t["priority"] = 5
            out.append({**t, "depends_on": t.get("depends_on", [])})
        return out

    def _default(self, goal: str) -> dict:
        return {"name":goal,"agent":"planner","priority":1,"data":{"goal":goal}}
