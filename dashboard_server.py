#!/usr/bin/env python3
# ੴ Amrit God Mode AI Dashboard Bootstrapper
import sys
from pathlib import Path

# Resolve paths
_base_dir = Path(__file__).resolve().parent
_subdirs = ["core", "agents", "memory", "learning", "punjabi", "voice", "failure", "dashboard", "os_ops", "utils", "config", "tests"]
for _sd in _subdirs:
    sys.path.insert(0, str(_base_dir / _sd))

if __name__ == "__main__":
    import uvicorn
    # Import and run the app
    uvicorn.run("dashboard.dashboard_server:app", host="0.0.0.0", port=8000, reload=True)
