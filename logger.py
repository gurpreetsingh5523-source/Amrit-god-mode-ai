"""Colored, leveled, file+console logger."""
import logging
import os
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

COLORS = {
    "DEBUG":    "\033[94m", "INFO":  "\033[92m",
    "WARNING":  "\033[93m", "ERROR": "\033[91m",
    "CRITICAL": "\033[95m", "RESET": "\033[0m",
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        c = COLORS.get(record.levelname, COLORS["RESET"])
        r = COLORS["RESET"]
        record.levelname = f"{c}{record.levelname:<8}{r}"
        record.name = f"\033[96m{record.name}\033[0m"
        return super().format(record)

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    ch = logging.StreamHandler()
    ch.setFormatter(ColorFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    fh = logging.FileHandler(LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(fh)
    return logger
