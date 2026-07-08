"""Information Extractor — Structured data from web pages."""
import re
import json
import urllib.request
import urllib.parse
from logger import setup_logger
logger = setup_logger("InfoExtractor")

class InformationExtractor:
    HEADERS = {"User-Agent": "Mozilla/5.0 (AMRIT-GODMODE/2.0)"}

    def fetch_text(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ", html)).strip()[:8000]
        except Exception:
            return ""

    def extract_emails(self, text: str) -> list:
        return list(set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)))

    def extract_phones(self, text: str) -> list:
        return list(set(re.findall(r'\+?\d[\d\s()-]{7,15}\d', text)))

    def extract_prices(self, text: str) -> list:
        return re.findall(r'[$€£¥]\s*[\d,]+(?:\.\d{2})?', text)

    def extract_dates(self, text: str) -> list:
        return re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}', text)

    def extract_links(self, html: str) -> list:
        hrefs = re.findall(r'href="(https?://[^"]+)"', html)
        return list(set(hrefs))[:50]

    def extract_structured(self, url: str) -> dict:
        text = self.fetch_text(url)
        return {"url":url,"emails":self.extract_emails(text),"phones":self.extract_phones(text),
                "prices":self.extract_prices(text),"dates":self.extract_dates(text),
                "word_count":len(text.split())}

    def extract_json_ld(self, html: str) -> list:
        blocks = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
        result = []
        for b in blocks:
            try:
                result.append(json.loads(b))
            except Exception:
                pass
        return result
