"""Research Agent — Web search, URL fetch, document analysis."""
import re, urllib.request, urllib.parse
from base_agent import BaseAgent

class ResearchAgent(BaseAgent):
    def __init__(self, eb, state): super().__init__("ResearchAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "search")
        query  = d.get("query") or task.get("name", "")
        await self.report(f"Research [{action}]: {query[:60]}")
        if action == "fetch_url": return await self._fetch(d.get("url",""))
        if action == "summarize": return await self._summarize(d.get("text",""), query)
        if action == "analyze":   return await self._analyze(query, d)
        return await self._search(query)

    async def _search(self, query: str) -> dict:
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                html = r.read().decode("utf-8", errors="ignore")
            titles   = re.findall(r'class="result__title"[^>]*>\s*<a[^>]*>(.*?)</a>', html, re.S)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</div>', html, re.S)
            results  = [{"title": re.sub(r'<[^>]+>','',t).strip(),
                         "snippet": re.sub(r'<[^>]+>','',s).strip()}
                        for t,s in zip(titles[:5], snippets[:5])]
        except Exception as e:
            self.logger.warning(f"Web search failed: {e}")
        ctx = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results) if results else ""
        if ctx:
            web_block = "Web results:\n" + ctx
        else:
            web_block = "Use your knowledge."
        summary = await self.ask_llm(f"Answer: {query}\n\n{web_block}")
        # Append to viral_content.md
        try:
            with open("workspace/viral_content.md", "a", encoding="utf-8") as f:
                f.write(f"\n\n# Research Summary\n\n{summary}\n")
        except Exception as e:
            pass
        return self.ok(query=query, results=results, summary=summary)

    async def _fetch(self, url: str) -> dict:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            text = re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ', html)).strip()[:5000]
            summary = await self._summarize(text, url)
            return self.ok(url=url, text=text, summary=summary)
        except Exception as e:
            return self.err(str(e))

    async def _summarize(self, text: str, topic: str = "") -> dict:
        s = await self.ask_llm(f"Summarize concisely{' about '+topic if topic else ''}:\n{text[:3000]}")
        return self.ok(summary=s, chars=len(text))

    async def _analyze(self, topic: str, d: dict) -> dict:
        a = await self.ask_llm(f"Deep analysis of: {topic}\nContext: {d.get('context','')}")
        return self.ok(topic=topic, analysis=a)
