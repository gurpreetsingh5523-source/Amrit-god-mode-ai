"""Ethical Guard — Multi-layer harmful action prevention."""
import re
from logger import setup_logger
logger = setup_logger("EthicalGuard")

BLOCKED_KW = ["rm -rf /","mkfs","dd if=/dev/zero",":(){ :|:& };:","format c:"]
BLOCKED_PAT = [r"delete\s+all\s+(files|data|system)",r"hack\s+(into|the)\s+\w+",
               r"(create|make)\s+(virus|malware|ransomware)",r"bypass\s+security",
               r"steal\s+(password|credential|data)",r"ddos|denial.of.service"]
WHITELIST   = [r"(research|study|test|learn)\s+about",r"explain\s+how",r"for\s+educational"]
SEVERITY    = {"CRITICAL":["malware","ransomware","rm -rf","exploit"],
               "HIGH":["hack","steal","ddos"],"MEDIUM":["bypass","phish"]}

class EthicalGuard:
    def __init__(self, strict=True): self.strict=strict; self._violations=[]

    def check(self, action: str) -> tuple:
        text = action.lower()
        for wp in WHITELIST:
            if re.search(wp,text): return True,"whitelisted"
        for kw in BLOCKED_KW:
            if kw in text: return self._block(action,f"Keyword: {kw!r}")
        for pat in BLOCKED_PAT:
            if re.search(pat,text): return self._block(action,f"Pattern: {pat}")
        return True,"allowed"

    def _block(self, action, reason):
        self._violations.append({"action":action[:100],"reason":reason})
        logger.warning(f"BLOCKED: {reason}")
        return False, reason

    def severity(self, action: str) -> str:
        t = action.lower()
        for sev,kws in SEVERITY.items():
            if any(k in t for k in kws): return sev
        return "LOW"

    def violations(self) -> list: return list(self._violations)
