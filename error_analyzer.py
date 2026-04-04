"""Error Analyzer — Root cause analysis for agent failures."""
import re
from logger import setup_logger
logger = setup_logger("ErrorAnalyzer")

class ErrorAnalyzer:
    def __init__(self): self._patterns = []

    def analyze(self, error: str, context: dict = None) -> dict:
        category = self._categorize(error)
        severity  = self._severity(error)
        suggestions = self._suggestions(category, error)
        return {"error":error,"category":category,"severity":severity,
                "suggestions":suggestions,"context":context or {}}

    def _categorize(self, error: str) -> str:
        e = error.lower()
        if "timeout" in e:    return "timeout"
        if "import" in e:     return "missing_dependency"
        if "permission" in e: return "permission_denied"
        if "not found" in e or "404" in e: return "not_found"
        if "memory" in e:     return "memory_error"
        if "connection" in e: return "network_error"
        if "syntax" in e:     return "syntax_error"
        if "key" in e or "index" in e: return "data_error"
        return "unknown"

    def _severity(self, error: str) -> str:
        e = error.lower()
        if any(w in e for w in ["crash","fatal","critical","killed"]): return "CRITICAL"
        if any(w in e for w in ["error","failed","exception"]):        return "HIGH"
        if any(w in e for w in ["warning","timeout"]):                 return "MEDIUM"
        return "LOW"

    def _suggestions(self, category: str, error: str) -> list:
        FIXES = {
            "timeout":            ["Increase timeout limit","Add retry logic","Break task into smaller chunks"],
            "missing_dependency": ["Run: pip install <package>","Check requirements.txt"],
            "permission_denied":  ["Check file permissions","Run with appropriate privileges"],
            "not_found":          ["Verify file/URL path","Check if resource exists"],
            "network_error":      ["Check internet connection","Verify URL/endpoint","Add retry with backoff"],
            "syntax_error":       ["Run code through linter","Check indentation"],
            "data_error":         ["Validate input data structure","Add null checks"],
        }
        return FIXES.get(category, ["Check logs for details","Add error handling","Retry operation"])

    def batch_analyze(self, errors: list) -> dict:
        results = [self.analyze(e.get("error","")) for e in errors]
        by_cat  = {}
        for r in results: by_cat.setdefault(r["category"],[]).append(r)
        return {"total":len(results),"by_category":by_cat,
                "most_common":max(by_cat,key=lambda k:len(by_cat[k])) if by_cat else "none"}
