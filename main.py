#!/usr/bin/env python3
# ੴ Amrit God Mode AI Bootstrapper
import os
import sys
import asyncio
from pathlib import Path

# Resolve paths
_base_dir = Path(__file__).resolve().parent
_subdirs = ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]
for _sd in _subdirs:
    sys.path.insert(0, str(_base_dir / _sd))

if __name__ == "__main__":
    from core.main import main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
