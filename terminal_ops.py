"""Terminal Operations — Safe command execution, output capture, process management."""
import subprocess
import os
from pathlib import Path
from logger import setup_logger
logger = setup_logger("TerminalOps")

BLOCKED_PATTERNS = [
    "rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:",
    "chmod 777 /", "chown root", "> /dev/sda"
]


class TerminalOps:
    """Safe terminal command execution with output capture."""

    def __init__(self, default_cwd: str = ".", timeout: int = 30):
        self.default_cwd = default_cwd
        self.timeout = timeout

    def run(self, command: str, cwd: str = None, timeout: int = None,
            capture: bool = True) -> dict:
        """
        Run a shell command safely.
        Returns {success, stdout, stderr, returncode, command}
        """
        # Safety check
        for blocked in BLOCKED_PATTERNS:
            if blocked in command:
                logger.warning(f"Blocked dangerous command: {command[:80]}")
                return {"success": False, "stdout": "", "stderr": "Blocked: dangerous command",
                        "returncode": -1, "command": command}

        cwd = cwd or self.default_cwd
        timeout = timeout or self.timeout
        logger.info(f"$ {command[:120]}")

        try:
            result = subprocess.run(
                command, shell=True, capture_output=capture,
                text=True, timeout=timeout, cwd=cwd
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:5000] if capture else "",
                "stderr": result.stderr[:2000] if capture else "",
                "returncode": result.returncode,
                "command": command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s",
                    "returncode": -1, "command": command}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e),
                    "returncode": -1, "command": command}

    def run_python(self, code: str, timeout: int = 15) -> dict:
        """Execute Python code snippet, return stdout/stderr."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                        delete=False, dir="/tmp") as f:
            f.write(code)
            tmp = f.name
        try:
            return self.run(f"python3 {tmp}", timeout=timeout)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def which(self, program: str) -> str:
        """Check if a program is installed, return its path or empty string."""
        import shutil
        return shutil.which(program) or ""

    def get_env(self, key: str, default: str = "") -> str:
        return os.environ.get(key, default)
