"""Search Engine — Multi-provider web search."""
import re
import json
import urllib.request
import urllib.parse
from logger import setup_logger
logger = setup_logger("SearchEngine")

class SearchEngine:
    def duckduckgo(self, query: str, n=8) -> list:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            titles   = [re.sub(r"<[^>]+>","",t).strip() for t in
                        re.findall(r'class="result__title".*?<a[^>]*>(.*?)</a>', html, re.S)][:n]
            snippets = [re.sub(r"<[^>]+>","",s).strip() for s in
                        re.findall(r'class="result__snippet"[^>]*>(.*?)</div>', html, re.S)][:n]
            urls     = re.findall(r'class="result__url"[^>]*>(.*?)</a>', html, re.S)[:n]
            return [{"title":t,"snippet":s,"url":u.strip()} for t,s,u in zip(titles,snippets,urls)]
        except Exception as e:
            logger.warning(f"Search error: {e}")
            return []

    def wikipedia_summary(self, query: str) -> dict:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                data = json.loads(r.read())
            return {"title":data.get("title"),"summary":data.get("extract"),
                    "url":data.get("content_urls",{}).get("desktop",{}).get("page")}
        except Exception as e:
            return {"error":str(e)}

    def news(self, topic: str) -> list:
        return self.duckduckgo(f"{topic} news latest")
