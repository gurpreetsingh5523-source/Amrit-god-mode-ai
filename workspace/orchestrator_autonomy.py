#!/usr/bin/env python3
"""Orchestrator for autonomous test runs.

This script will:
 - create a local virtualenv at .venv (if missing)
 - install project requirements (if requirements.txt exists)
 - install pytest and pytest-asyncio
 - run pytest and save output to workspace/test_output/pytest_output.txt

Designed to be executed locally by the repository owner (no sudo).
It is safe: non-destructive by default and writes logs under `workspace/test_output`.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

# optional adblocker control: dynamic import from workspace/adblocker/ad_shield.py
_ad_shield = None
def get_ad_shield():
    global _ad_shield
    if _ad_shield is not None:
        return _ad_shield
    # Try to load module from workspace/adblocker/ad_shield.py
    import importlib.util
    mod_path = os.path.join(os.path.dirname(__file__), "adblocker", "ad_shield.py")
    if not os.path.isfile(mod_path):
        return None
    spec = importlib.util.spec_from_file_location("ad_shield", mod_path)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore
        _ad_shield = mod
        return _ad_shield
    except Exception:
        return None


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_DIR = os.path.join(ROOT, ".venv")
PYTHON = os.path.join(VENV_DIR, "bin", "python")
PIP = os.path.join(VENV_DIR, "bin", "pip")
OUT_DIR = os.path.join(ROOT, "workspace", "test_output")
PYTEST_OUTPUT = os.path.join(OUT_DIR, "pytest_output.txt")


def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def run_cmd(cmd, env=None, cwd=None, capture=False):
    print(f">> Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE if capture else None,
                         stderr=subprocess.STDOUT if capture else None, text=True)
    if capture:
        return res.returncode, res.stdout
    return res.returncode, None


def create_venv(dry_run=False):
    if os.path.isdir(VENV_DIR):
        print(f"Virtualenv already exists at {VENV_DIR}")
        return True
    if dry_run:
        print(f"[dry-run] would create venv at {VENV_DIR}")
        return True
    print("Creating virtualenv...")
    rc, _ = run_cmd([sys.executable, "-m", "venv", VENV_DIR])
    return rc == 0


def install_packages(dry_run=False):
    if dry_run:
        print("[dry-run] would upgrade pip and install requirements + pytest")
        return True
    print("Upgrading pip, setuptools, wheel...")
    rc, _ = run_cmd([sys.executable, "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"], capture=True)
    if rc != 0:
        print("Warning: pip upgrade failed (continuing)")
    # install requirements if present
    req = os.path.join(ROOT, "requirements.txt")
    if os.path.isfile(req):
        print("Installing requirements.txt...")
        rc, out = run_cmd([sys.executable, "-m", "pip", "install", "-r", req], capture=True)
        if rc != 0:
            print("requirements install had errors; continuing. See output below:\n")
            print(out)
    # install pytest into venv
    print("Installing pytest and pytest-asyncio into venv...")
    # ensure pip from venv exists
    if not os.path.isfile(PIP):
        print("pip not found in venv; attempting to use venv python -m pip")
        rc, out = run_cmd([sys.executable, "-m", "pip", "install", "pytest", "pytest-asyncio"], capture=True)
    else:
        rc, out = run_cmd([PIP, "install", "pytest", "pytest-asyncio"], capture=True)
    if rc != 0:
        print("Failed to install pytest:\n", out)
        return False
    return True


def run_pytest(dry_run=False):
    ensure_out_dir()
    header = f"Pytest run at {datetime.utcnow().isoformat()}Z\n"
    if dry_run:
        with open(PYTEST_OUTPUT, "w") as f:
            f.write(header)
            f.write("[dry-run] pytest not executed.\n")
        print(f"[dry-run] wrote placeholder output to {PYTEST_OUTPUT}")
        return 0

    print("Running pytest (this may take a while)...")
    # use the venv python to run pytest if available, otherwise system python
    python_exec = PYTHON if os.path.isfile(PYTHON) else sys.executable
    cmd = [python_exec, "-m", "pytest", "-q"]
    rc, out = run_cmd(cmd, capture=True, cwd=ROOT)
    with open(PYTEST_OUTPUT, "w") as f:
        f.write(header)
        f.write(out or "")
    print(f"Pytest finished with exit code {rc}. Output saved to {PYTEST_OUTPUT}")
    return rc


def main():
    parser = argparse.ArgumentParser(description="Orchestrator: create venv and run tests or control adblocker")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute destructive actions; just show plan")
    parser.add_argument("--enable-adblock", action="store_true", help="Enable system adblock using /etc/hosts (requires sudo when running)")
    parser.add_argument("--disable-adblock", action="store_true", help="Disable AMRIT adblock block from /etc/hosts (requires sudo when running)")
    args = parser.parse_args()

    ensure_out_dir()

    # Handle adblock commands first
    if args.enable_adblock or args.disable_adblock:
        ad_mod = get_ad_shield()
        if ad_mod is None:
            print("Adblocker module not available. Please ensure workspace/adblocker/ad_shield.py exists.")
            sys.exit(2)
        if args.enable_adblock:
            print("Enabling adblock via ad_shield (will require sudo when executed)")
            # call module enable (it will request root or exit with message)
            ad_mod.enable()
            sys.exit(0)
        if args.disable_adblock:
            print("Disabling adblock via ad_shield (will require sudo when executed)")
            ad_mod.disable()
            sys.exit(0)

    ok = create_venv(dry_run=args.dry_run)
    if not ok:
        print("Failed to create virtualenv. Aborting.")
        sys.exit(1)

    ok = install_packages(dry_run=args.dry_run)
    if not ok:
        print("Failed to install required packages. Aborting.")
        sys.exit(1)

    rc = run_pytest(dry_run=args.dry_run)
    if rc == 0:
        print("All tests passed (exit code 0)")
    else:
        print(f"Some tests failed (exit code {rc}). See {PYTEST_OUTPUT} for details.")
    sys.exit(rc)


if __name__ == "__main__":
    main()
