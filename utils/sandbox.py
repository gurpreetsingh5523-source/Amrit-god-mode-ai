"""Sandbox — Safe isolated code execution."""
import subprocess
import tempfile
import os
import sys
from logger import setup_logger
logger = setup_logger("Sandbox")

FORBIDDEN = ["os.system","subprocess.call","__import__('os')",
             "shutil.rmtree","open('/etc","open('/var"]

class Sandbox:
    def __init__(self, timeout=10, max_out=5000):
        self.timeout=timeout
        self.max_out=max_out

    def is_safe(self, code: str) -> tuple:
        for f in FORBIDDEN:
            if f in code:
                return False, f"Forbidden: {f!r}"
        return True, "ok"

    def run(self, code: str, language="python") -> dict:
        safe, reason = self.is_safe(code)
        if not safe:
            return {"stdout":"","stderr":f"BLOCKED: {reason}","returncode":-2}
        return self._python(code) if language=="python" else self._bash(code)

    def _python(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".py",delete=False,mode="w") as f:
            f.write(code)
            tmp=f.name
        try:
            r = subprocess.run([sys.executable,tmp],capture_output=True,text=True,timeout=self.timeout)
            return {"stdout":r.stdout[:self.max_out],"stderr":r.stderr[:1000],
                    "returncode":r.returncode,"success":r.returncode==0}
        except subprocess.TimeoutExpired:
            return {"stdout":"","stderr":"Timeout","returncode":-1}
        except Exception as e:
            return {"stdout":"","stderr":str(e),"returncode":-1}
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def _bash(self, code: str) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".sh",delete=False,mode="w") as f:
            f.write("#!/bin/bash\nset -e\n"+code)
            tmp=f.name
        os.chmod(tmp,0o700)
        try:
            r = subprocess.run(["bash",tmp],capture_output=True,text=True,timeout=self.timeout)
            return {"stdout":r.stdout[:self.max_out],"stderr":r.stderr[:1000],"returncode":r.returncode}
        except subprocess.TimeoutExpired:
            return {"stdout":"","stderr":"Bash timeout","returncode":-1}
        except Exception as e:
            return {"stdout":"","stderr":str(e),"returncode":-1}
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
