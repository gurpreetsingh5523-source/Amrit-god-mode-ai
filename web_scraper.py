"""Web Scraper — HTML parsing and structured data extraction."""
import re
import urllib.request
import urllib.parse
from logger import setup_logger
logger = setup_logger("WebScraper")

class WebScraper:
    def __init__(self, timeout=10): self.timeout=timeout
    HEADERS = {"User-Agent":"Mozilla/5.0 (AMRIT-GODMODE/2.0)"}

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Fetch failed: {e}")
            return ""

    def text(self, url: str) -> str:
        html = self.fetch(url)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()[:5000]

    def links(self, url: str) -> list:
        html = self.fetch(url)
        return list(set(re.findall(r'href="(https?://[^"]+)"', html)))

    def extract_emails(self, url: str) -> list:
        text = self.fetch(url)
        return list(set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)))

    def extract_phones(self, url: str) -> list:
        text = self.fetch(url)
        return list(set(re.findall(r'\+?\d[\d\s()-]{7,15}\d', text)))

    def get_json(self, url: str, params=None) -> dict:
        import json
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"error": str(e)}

    def download(self, url: str, path: str) -> bool:
        try:
            urllib.request.urlretrieve(url, path)
            return True
        except Exception:
            return False
