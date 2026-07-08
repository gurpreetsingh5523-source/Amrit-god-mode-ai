import os
import sys
from pathlib import Path

# Resolve paths and add all subdirs to sys.path so pytest can import everything correctly
_base_dir = Path(__file__).resolve().parent.parent
_subdirs = ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]
for _sd in _subdirs:
    sys.path.insert(0, str(_base_dir / _sd))
