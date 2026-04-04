"""Crawler — Multi-depth web crawler with link extraction."""
import re, urllib.request
from logger import setup_logger
logger = setup_logger("Crawler")

class Crawler:
    def __init__(self, max_pages=20, timeout=8):
        self.max_pages=max_pages; self.timeout=timeout
        self.headers={"User-Agent":"Mozilla/5.0 (AMRIT-GODMODE)"}

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except: return ""

    def text(self, html: str) -> str:
        return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ", html)).strip()

    def links(self, html: str, base_url: str="") -> list:
        all_links = re.findall(r'href="(https?://[^"]+)"', html)
        return list(set(all_links))[:20]

    async def crawl(self, start_url: str, depth=1) -> list:
        visited = set(); pages = []

        async def _crawl(url, d):
            if url in visited or d < 0 or len(pages) >= self.max_pages: return
            visited.add(url)
            html  = self.fetch(url)
            text  = self.text(html)[:1000]
            links = self.links(html, url)[:5]
            pages.append({"url":url,"text":text,"links":links,"depth":depth-d})
            logger.info(f"Crawled: {url}")
            if d > 0:
                for link in links[:3]:
                    await _crawl(link, d-1)

        await _crawl(start_url, depth)
        return pages

    def sitemap(self, domain: str) -> list:
        sm_url = f"{domain.rstrip('/')}/sitemap.xml"
        html = self.fetch(sm_url)
        return re.findall(r"<loc>(.*?)</loc>", html)[:50]
