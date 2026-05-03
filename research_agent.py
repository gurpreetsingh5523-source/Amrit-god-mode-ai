"""Research Agent — Web search, URL fetch, document analysis."""
import re
import urllib.request
import urllib.parse
from base_agent import BaseAgent

class ResearchAgent(BaseAgent):
    def __init__(self, eb, state): super().__init__("ResearchAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "search")
        query  = d.get("query") or task.get("name", "")
        await self.report(f"[START] Research [{action}]: {query[:60]}", level="debug")
        try:
            if action == "fetch_url":
                result = await self._fetch(d.get("url",""))
            elif action == "summarize":
                result = await self._summarize(d.get("text",""), query)
            elif action == "analyze":
                result = await self._analyze(query, d)
            else:
                result = await self._search(query)
            await self.report(f"[END] Research [{action}]: {query[:60]}", level="debug")
            return result
        except Exception as e:
            await self.report(f"[ERROR] Research [{action}]: {query[:60]} | {e}", level="error")
            return self.err(str(e))

    async def _search(self, query: str) -> dict:
        await self.report(f"[START] _search: {query[:60]}", level="debug")
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                html = r.read().decode("utf-8", errors="ignore")
            titles   = re.findall(r'class="result__title"[^>]*>\s*<a[^>]*>(.*?)</a>', html, re.S)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</div>', html, re.S)
            results  = [{"title": re.sub(r'<[^>]+>', '', t).strip(),
                         "snippet": re.sub(r'<[^>]+>', '', s).strip()}
                        for t,s in zip(titles[:5], snippets[:5])]
        except Exception as e:
            await self.report(f"[ERROR] _search: {query[:60]} | {e}", level="error")
            return self.err(str(e))
        ctx = "\n".join(f"- {r['title']}: {r['snippet']}" for r in results) if results else ""
        if ctx:
            web_block = "Web results:\n" + ctx
        else:
            web_block = "Use your knowledge."
        try:
            summary = await self.ask_llm(f"Answer: {query}\n\n{web_block}")
        except Exception as e:
            await self.report(f"[ERROR] _search LLM: {query[:60]} | {e}", level="error")
            return self.err(f"LLM error: {e}")
        try:
            with open("workspace/viral_content.md", "a", encoding="utf-8") as f:
                f.write(f"\n\n# Research Summary\n\n{summary}\n")
        except Exception:
            pass
        await self.report(f"[END] _search: {query[:60]}", level="debug")
        return self.ok(query=query, results=results, summary=summary)

    async def _fetch(self, url: str) -> dict:
        await self.report(f"[START] _fetch: {url[:60]}", level="debug")
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            text = re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ', html)).strip()[:5000]
            try:
                summary = await self._summarize(text, url)
            except Exception as e:
                await self.report(f"[ERROR] _fetch LLM: {url[:60]} | {e}", level="error")
                return self.err(f"LLM error: {e}")
            await self.report(f"[END] _fetch: {url[:60]}", level="debug")
            return self.ok(url=url, text=text, summary=summary)
        except Exception as e:
            await self.report(f"[ERROR] _fetch: {url[:60]} | {e}", level="error")
            return self.err(str(e))

    async def _summarize(self, text: str, topic: str = "") -> dict:
        await self.report(f"[START] _summarize: {topic[:60]}", level="debug")
        try:
            s = await self.ask_llm(f"Summarize concisely{' about '+topic if topic else ''}:\n{text[:3000]}")
        except Exception as e:
            await self.report(f"[ERROR] _summarize LLM: {topic[:60]} | {e}", level="error")
            return self.err(f"LLM error: {e}")
        await self.report(f"[END] _summarize: {topic[:60]}", level="debug")
        return self.ok(summary=s, chars=len(text))

    async def _analyze(self, topic: str, d: dict) -> dict:
        await self.report(f"[START] _analyze: {topic[:60]}", level="debug")
        try:
            a = await self.ask_llm(f"Deep analysis of: {topic}\nContext: {d.get('context','')}")
        except Exception as e:
            await self.report(f"[ERROR] _analyze LLM: {topic[:60]} | {e}", level="error")
            return self.err(f"LLM error: {e}")
        await self.report(f"[END] _analyze: {topic[:60]}", level="debug")
        return self.ok(topic=topic, analysis=a)
