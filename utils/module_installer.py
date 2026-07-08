"""Module Installer — Installs Python packages on demand."""
import subprocess
from logger import setup_logger
logger = setup_logger("ModuleInstaller")

SAFE_PACKAGES = {
    "requests","pandas","numpy","pillow",
    "pyyaml","psutil","sentence-transformers","chromadb",
    "playwright","beautifulsoup4","scikit-learn","torch","transformers",
    "datasets","openpyxl","pyarrow","aiofiles","httpx","pyttsx3",
    "SpeechRecognition","openai-whisper","opencv-python","pytesseract"
}

class ModuleInstaller:
    def __init__(self): self._installed = []

    def install(self, package: str, force=False) -> dict:
        base = package.split("[")[0].split(">=")[0].split("==")[0].strip()
        if not force and base not in SAFE_PACKAGES:
            return {"status":"blocked","reason":f"{base} not in safe list"}
        try:
            r = subprocess.run(["pip","install",package,"-q"],capture_output=True,text=True,timeout=120)
            success = r.returncode == 0
            if success:
                self._installed.append(package)
            logger.info(f"Installed: {package}")
            return {"status":"installed" if success else "failed",
                    "package":package,"output":r.stdout+r.stderr}
        except subprocess.TimeoutExpired:
            return {"status":"timeout","package":package}
        except Exception as e:
            return {"status":"error","package":package,"error":str(e)}

    def install_from_requirements(self, path="requirements.txt") -> dict:
        from pathlib import Path
        reqs = Path(path).read_text().splitlines()
        results = []
        for req in reqs:
            req = req.strip()
            if req and not req.startswith("#"):
                results.append(self.install(req))
        return {"results":results,"installed":len([r for r in results if r["status"]=="installed"])}

    def is_installed(self, package: str) -> bool:
        try:
            __import__(package)
            return True
        except ImportError:
            return False

    def history(self) -> list:
        return list(self._installed)
