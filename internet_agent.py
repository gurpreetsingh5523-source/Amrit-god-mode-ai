import asyncio
"""Internet Agent — Deep web crawling, scientific research, multi-source data extraction."""
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from base_agent import BaseAgent

class InternetAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("InternetAgent", eb, state)
        self._browser = None  # lazy BrowserOps instance

    def _get_browser(self):
        if self._browser is None:
            try:
                from browser_ops import BrowserOps
                self._browser = BrowserOps(headless=True)
            except Exception as e:
                self.logger.warning(f"BrowserOps unavailable: {e}")
                self._browser = False
        return self._browser if self._browser else None

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "search")
        await self.report(f"Internet [{action}]")
        if action == "search":
            return await self._search(d.get("query",""))
        if action == "browse":
            return await self._browse(d.get("url",""), d.get("query",""))
        if action == "crawl":
            return await self._crawl(d.get("url",""), d.get("depth",1))
        if action == "extract":
            return await self._extract(d.get("url",""), d.get("fields",[]))
        if action == "news":
            return await self._news(d.get("topic",""))
        if action == "wikipedia":
            return await self._wikipedia(d.get("query",""))
        if action == "download":
            return await self._download(d.get("url",""), d.get("dest","workspace/"))
        if action == "arxiv":
            return await self._arxiv(d.get("query",""), d.get("max_results",5))
        if action == "pubmed":
            return await self._pubmed(d.get("query",""), d.get("max_results",5))
        if action == "scholar":
            return await self._scholar_search(d.get("query",""))
        return await self._search(d.get("query", task.get("name","")))

    async def _browse(self, url: str, query: str = "") -> dict:
        """Use real browser (Selenium) to load a JS-heavy page and extract text."""
        browser = self._get_browser()
        if not browser:
            # Fallback to urllib crawl
            return await self._crawl(url, depth=0)
        try:
            ok = browser.navigate(url, wait=2.0)
            if not ok:
                return self.err(f"Could not navigate to {url}")
            text = browser.get_page_text()
            title = browser.get_title()
            current_url = browser.get_current_url()
            answer = ""
            if query and text:
                answer = await self.ask_llm(
                    f"From this webpage, answer: {query}\n\nPage content:\n{text[:3000]}"
                )
            return self.ok(url=current_url, title=title, text=text, answer=answer)
        except Exception as e:
            self.logger.warning(f"Browse failed: {e}")
            return await self._crawl(url, depth=0)
        finally:
            browser.close_browser()

    async def _search(self, query: str) -> dict:
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            titles   = [re.sub(r'<[^>]+>','',t).strip() for t in
                        re.findall(r'class="result__title".*?<a[^>]*>(.*?)</a>', html, re.S)][:6]
            snippets = [re.sub(r'<[^>]+>','',s).strip() for s in
                        re.findall(r'class="result__snippet"[^>]*>(.*?)</div>', html, re.S)][:6]
            urls     = re.findall(r'class="result__url"[^>]*>(.*?)</a>', html, re.S)[:6]
            results  = [{"title":t,"snippet":s,"url":u.strip()}
                        for t,s,u in zip(titles,snippets,urls)]
        except Exception as e:
            self.logger.warning(f"Search failed: {e}")
        ctx = "\n".join(f"• {r['title']}: {r['snippet']}" for r in results)
        answer = await self.ask_llm(f"Based on web results, answer: {query}\n\n{ctx}")
        return self.ok(query=query, results=results, answer=answer)

    async def _crawl(self, url: str, depth: int = 1) -> dict:
        visited, pages = set(), []
        async def crawl_page(u, d):
            if u in visited or d < 0:
                return
            visited.add(u)
            try:
                self.logger.info(f"Crawling {u} with depth {d}")
                req = urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    html = r.read().decode("utf-8", errors="ignore")
                self.logger.debug(f"Extracting text from {u}")
                text  = re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ', html)).strip()[:2000]
                self.logger.debug(f"Finding links on {u}")
                links = list(set(re.findall(r'href="(https?://[^"]+)"', html)))[:5]
                pages.append({"url": u, "text": text[:500], "links": links})
                if d > 0:
                    for link in links[:3]:
                        await crawl_page(link, d-1)
            except Exception as e:
                self.logger.error(f"Error crawling {u}: {str(e)}")
                pages.append({"url": u, "error": str(e)})
        await crawl_page(url, depth)
        return self.ok(url=url, pages_crawled=len(pages), pages=pages)

    async def _extract(self, url: str, fields: list) -> dict:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            text = re.sub(r'\s+',' ', re.sub(r'<[^>]+>',' ', html)).strip()[:4000]
            prompt = f"Extract these fields from the text: {fields}\nText: {text}\nReturn JSON."
            extracted = await self.ask_llm(prompt)
            return self.ok(url=url, fields=fields, extracted=extracted)
        except Exception as e:
            return self.err(str(e))

    async def _news(self, topic: str) -> dict:
        return await self._search(f"{topic} news latest 2024")

    async def _wikipedia(self, query: str) -> dict:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
            with urllib.request.urlopen(url, timeout=8) as r:
                data = json.loads(r.read())
            return self.ok(title=data.get("title",""),
                           summary=data.get("extract",""),
                           url=data.get("content_urls",{}).get("desktop",{}).get("page",""))
        except Exception as e:
            return self.err(str(e))

    async def _download(self, url: str, dest: str) -> dict:
        try:
            from pathlib import Path
            Path(dest).mkdir(parents=True, exist_ok=True)
            filename = url.split("/")[-1] or "downloaded_file"
            filepath = f"{dest}/{filename}"
            urllib.request.urlretrieve(url, filepath)
            return self.ok(url=url, saved=filepath)
        except Exception as e:
            return self.err(str(e))

    async def interactive_loop(self, orchestrator):
        print("\n\033[96m🌐 Internet Mode\033[0m")
        while True:
            q = input("\n[Internet] Query (or exit): ").strip()
            if q.lower() == "exit":
                break
            r = await self._search(q)
            print(f"\n{r.get('answer','')}\n")

    # ══════════════════════════════════════════════════════════════
    # SCIENTIFIC SEARCH — arXiv, PubMed, Scholar
    # ══════════════════════════════════════════════════════════════

    async def _arxiv(self, query: str, max_results: int = 5) -> dict:
        """Search arXiv for latest research papers."""
        papers = []
        try:
            q = urllib.parse.quote(query)
            url = (f"http://export.arxiv.org/api/query?search_query=all:{q}"
                   f"&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending")
            req = urllib.request.Request(url, headers={"User-Agent": "AMRIT-GODMODE/2.1"})
            with urllib.request.urlopen(req, timeout=15) as r:
                xml_data = r.read().decode("utf-8")

            root = ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)
                link = entry.find("atom:id", ns)
                authors = entry.findall("atom:author/atom:name", ns)
                categories = entry.findall("atom:category", ns)

                paper = {
                    "title": title.text.strip().replace("\n", " ") if title is not None else "",
                    "abstract": summary.text.strip()[:500] if summary is not None else "",
                    "date": published.text[:10] if published is not None else "",
                    "url": link.text.strip() if link is not None else "",
                    "authors": [a.text for a in authors[:3]],
                    "categories": [c.get("term", "") for c in categories[:3]],
                }
                papers.append(paper)

            self.logger.info(f"arXiv: found {len(papers)} papers for '{query}'")
        except Exception as e:
            self.logger.warning(f"arXiv search failed: {e}")

        # Summarize findings
        if papers:
            ctx = "\n\n".join(
                f"📄 {p['title']} ({p['date']})\n"
                f"   Authors: {', '.join(p['authors'])}\n"
                f"   {p['abstract'][:200]}"
                for p in papers
            )
            summary = await self.ask_llm(
                f"Summarize these research papers about '{query}':\n{ctx}\n\n"
                "What are the key findings and trends?"
            )
        else:
            summary = f"No arXiv papers found for '{query}'"

        return self.ok(query=query, source="arxiv", papers=papers, summary=summary)

    async def _pubmed(self, query: str, max_results: int = 5) -> dict:
        """Search PubMed for biomedical research papers."""
        papers = []
        try:
            # Step 1: Search for IDs
            q = urllib.parse.quote(query)
            search_url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
                          f"db=pubmed&term={q}&retmax={max_results}&sort=date&retmode=json")
            req = urllib.request.Request(search_url, headers={"User-Agent": "AMRIT-GODMODE/2.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())

            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return self.ok(query=query, source="pubmed", papers=[], summary="No results found")

            # Step 2: Fetch summaries
            id_str = ",".join(ids)
            fetch_url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
                         f"db=pubmed&id={id_str}&retmode=json")
            req = urllib.request.Request(fetch_url, headers={"User-Agent": "AMRIT-GODMODE/2.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                summaries = json.loads(r.read())

            for pid in ids:
                info = summaries.get("result", {}).get(pid, {})
                if not isinstance(info, dict):
                    continue
                authors = info.get("authors", [])
                paper = {
                    "title": info.get("title", ""),
                    "date": info.get("pubdate", ""),
                    "journal": info.get("fulljournalname", ""),
                    "authors": [a.get("name", "") for a in authors[:3]] if isinstance(authors, list) else [],
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    "pmid": pid,
                }
                papers.append(paper)

            self.logger.info(f"PubMed: found {len(papers)} papers for '{query}'")
        except Exception as e:
            self.logger.warning(f"PubMed search failed: {e}")

        if papers:
            ctx = "\n".join(f"📄 {p['title']} ({p['date']}) — {p['journal']}" for p in papers)
            summary = await self.ask_llm(
                f"Summarize these medical/biomedical papers about '{query}':\n{ctx}\n\n"
                "Key findings, trends, and clinical relevance?"
            )
        else:
            summary = f"No PubMed papers found for '{query}'"

        return self.ok(query=query, source="pubmed", papers=papers, summary=summary)

    async def _scholar_search(self, query: str) -> dict:
        """Search for academic papers via DuckDuckGo targeting scholarly content."""
        scholarly_query = f"site:scholar.google.com OR site:arxiv.org OR site:pubmed.ncbi.nlm.nih.gov {query}"
        result = await self._search(scholarly_query)
        result["source"] = "scholar"
        return result