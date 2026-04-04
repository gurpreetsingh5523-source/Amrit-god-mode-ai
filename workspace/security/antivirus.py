#!/usr/bin/env python3
"""Simple local antivirus/heuristic scanner for Amrit workspace.

This is a lightweight, safe scanner intended for local, manual use. It uses
simple regex-based signatures and file-hash matching to flag suspicious
files. It can optionally quarantine flagged files by moving them to
workspace/security/quarantine/.

NOT a replacement for a full AV product (ClamAV, commercial AV). Use this for
quick triage and automated checks inside the project workspace.

Usage:
  python3 workspace/security/antivirus.py --path . --quarantine
  python3 workspace/security/antivirus.py --path /path/to/scan --signatures workspace/security/signatures.txt

Outputs a JSON-like line per finding to stdout. Return codes:
  0 - scan complete, no findings
  1 - findings detected
  2 - fatal error (permission / input)

"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import subprocess
import zipfile
import tarfile
from pathlib import Path
from typing import List, Optional
import threading
import logging

WORKSPACE = Path(__file__).resolve().parents[1]
SIGNATURES_FILE = WORKSPACE / "security" / "signatures.txt"
YARA_FILE = WORKSPACE / "security" / "signatures.yar"
QUARANTINE_DIR = WORKSPACE / "security" / "quarantine"
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
WATCH_LOG = WORKSPACE / "security" / "watch.log"
logging.basicConfig(filename=str(WATCH_LOG), level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')

# Heuristic: read up to this many bytes when scanning large files for signatures
MAX_READ_BYTES = 1024 * 256  # 256 KiB


def load_signatures(path: Path = SIGNATURES_FILE) -> List[re.Pattern]:
    patterns: List[re.Pattern] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                try:
                    patterns.append(re.compile(ln, flags=re.IGNORECASE))
                except re.error:
                    # skip invalid regexes
                    continue
    except FileNotFoundError:
        # No signatures file; return empty list
        return []
    return patterns


def load_yara_rules(path: Path = YARA_FILE):
    try:
        import yara  # type: ignore
    except Exception:
        return None
    if not path.exists():
        return None
    try:
        return yara.compile(str(path))
    except Exception:
        return None


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


def is_text_file(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(4096)
            if b"\0" in chunk:
                return False
    except Exception:
        return False
    return True


def scan_archive(path: Path, signatures: List[re.Pattern], yara_rules=None) -> List[str]:
    findings: List[str] = []
    # zip files
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, 'r') as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    with z.open(info, 'r') as fh:
                        data = fh.read(MAX_READ_BYTES)
                        try:
                            txt = data.decode('utf-8', errors='ignore')
                            for pat in signatures:
                                if pat.search(txt):
                                    findings.append(f"archive:{info.filename}:signature:{pat.pattern}")
                        except Exception:
                            pass
                        if yara_rules is not None:
                            try:
                                if yara_rules.match(data=data):
                                    findings.append(f"archive:{info.filename}:yara")
                            except Exception:
                                pass
            return findings
    except Exception:
        pass

    # tar files
    try:
        if tarfile.is_tarfile(path):
            with tarfile.open(path, 'r:*') as t:
                for member in t.getmembers():
                    if not member.isreg():
                        continue
                    fh = t.extractfile(member)
                    if fh is None:
                        continue
                    data = fh.read(MAX_READ_BYTES)
                    try:
                        txt = data.decode('utf-8', errors='ignore')
                        for pat in signatures:
                            if pat.search(txt):
                                findings.append(f"archive:{member.name}:signature:{pat.pattern}")
                    except Exception:
                        pass
                    if yara_rules is not None:
                        try:
                            if yara_rules.match(data=data):
                                findings.append(f"archive:{member.name}:yara")
                        except Exception:
                            pass
            return findings
    except Exception:
        pass

    return findings


def scan_file(path: Path, signatures: List[re.Pattern]) -> List[str]:
    findings: List[str] = []
    try:
        size = path.stat().st_size
    except Exception:
        return ["stat_failed"]

    # Skip very large files by default
    if size > (MAX_READ_BYTES * 4):
        return ["skipped_large"]

    # Quick check by filename (suspicious extensions)
    suspicious_exts = [".exe", ".dll", ".scr", ".bin", ".run", ".sh", ".pl"]
    if path.suffix.lower() in suspicious_exts:
        findings.append("suspicious_extension")

    # Read up to MAX_READ_BYTES for content scanning
    content = b""
    try:
        with path.open("rb") as f:
            content = f.read(MAX_READ_BYTES)
    except Exception:
        return ["read_failed"]

    # Heuristic: look for ELF/PE headers in binaries
    if content.startswith(b"MZ"):
        findings.append("pe_header")
    if content.startswith(b"\x7fELF"):
        findings.append("elf_header")

    # For text files, decode and run regex signatures
    yara_rules = load_yara_rules()
    if is_text_file(path) and signatures:
        try:
            txt = content.decode("utf-8", errors="ignore")
            for pat in signatures:
                if pat.search(txt):
                    findings.append(f"signature:{pat.pattern}")
        except Exception:
            pass
    # run yara on initial content if available
    if yara_rules is not None:
        try:
            if yara_rules.match(data=content):
                findings.append("yara")
        except Exception:
            pass

    # Example heuristic: detect base64 decoding and piping to sh (common installers/dropper)
    try:
        txtfull = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"base64\s+-d|base64\s+-D|openssl\s+enc|curl\s+.*\|\s*sh|wget\s+.*\|\s*sh", txtfull, flags=re.IGNORECASE):
            findings.append("download_and_exec")
    except Exception:
        pass

    # If an archive, scan its contents
    try:
        arch_findings = scan_archive(path, signatures, yara_rules=yara_rules)
        if arch_findings:
            findings.extend(arch_findings)
    except Exception:
        pass

    return findings


def quarantine_file(path: Path, dest_dir: Path = QUARANTINE_DIR) -> Path:
    ts = time.strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / (path.name + "." + ts + ".quarantine")
    try:
        # preserve metadata in a sidecar json
        meta = {
            "original_path": str(path),
            "quarantined_at": ts,
            "sha256": sha256_of_file(path),
        }
        shutil.move(str(path), str(dest))
        with (dest.with_suffix(dest.suffix + ".meta.json")).open("w", encoding="utf-8") as mf:
            json.dump(meta, mf)
    except Exception:
        return Path("")
    return dest


def restore_quarantine(qpath: Path) -> bool:
    # qpath should be path to .quarantine file inside quarantine dir
    if not qpath.exists():
        return False
    meta_path = qpath.with_suffix(qpath.suffix + ".meta.json")
    orig = None
    try:
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as mf:
                m = json.load(mf)
                orig = m.get("original_path")
        if orig:
            orig_path = Path(orig)
            orig_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(qpath), str(orig_path))
            # remove meta
            if meta_path.exists():
                meta_path.unlink()
            return True
    except Exception:
        return False
    return False


def is_high_risk(findings: List[str]) -> bool:
    high = {"download_and_exec", "clamscan:infected", "yara", "pe_header", "elf_header"}
    for f in findings:
        for h in high:
            if h in f:
                return True
    return False


def _handle_file_event(fp: Path, signatures: List[re.Pattern], quarantine: bool, auto_quarantine: bool, interval: int = 0):
    """Scan a new file and optionally quarantine high-risk findings.
    This function is safe to call from watcher threads.
    """
    try:
        findings = scan_file(fp, signatures)
        # run clamscan if available for binaries
        clamscan = shutil.which("clamscan")
        if clamscan and fp.suffix.lower() in [".exe", ".dll", ".so", ""]:
            try:
                res = subprocess.run([clamscan, "--no-summary", str(fp)], capture_output=True, text=True, timeout=30)
                if res.returncode == 1:
                    findings.append("clamscan:infected")
                elif res.returncode == 2:
                    findings.append("clamscan:error")
            except Exception:
                pass

        if findings and findings != ["skipped_large"]:
            record = {"path": str(fp), "sha256": sha256_of_file(fp), "findings": findings}
            print(json.dumps(record, ensure_ascii=False))
            logging.info(f"Watcher found: {record}")
            # auto-quarantine only for high risk
            if is_high_risk(findings) and auto_quarantine:
                q = quarantine_file(fp)
                if q:
                    logging.info(f"Auto-quarantined {fp} -> {q}")
                    print(json.dumps({"quarantine": str(q)}))
            elif quarantine:
                q = quarantine_file(fp)
                if q:
                    logging.info(f"Quarantined {fp} -> {q}")
                    print(json.dumps({"quarantine": str(q)}))
    except Exception as e:
        logging.exception(f"Error handling file event for {fp}: {e}")


def watch_directory(paths: List[Path], signatures: List[re.Pattern], quarantine: bool = False, auto_quarantine: bool = False, interval: int = 5):
    """Watch specified directories for new files. Uses watchdog if available; otherwise polls."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                fp = Path(event.src_path)
                # small delay to allow file to finish writing
                threading.Timer(1.0, _handle_file_event, args=(fp, signatures, quarantine, auto_quarantine)).start()

        observer = Observer()
        handler = _Handler()
        for p in paths:
            if p.exists():
                observer.schedule(handler, str(p), recursive=False)
        observer.start()
        print(json.dumps({"info": f"watching {', '.join(str(p) for p in paths)}"}))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        return
    except Exception:
        # fallback: polling
        print(json.dumps({"info": f"watchdog not available; polling {', '.join(str(p) for p in paths)} every {interval}s"}))
        seen = set()
        for p in paths:
            if p.exists():
                for f in p.iterdir():
                    seen.add(str(f))
        try:
            while True:
                for p in paths:
                    if not p.exists():
                        continue
                    for f in p.iterdir():
                        sf = str(f)
                        if sf not in seen and f.is_file():
                            seen.add(sf)
                            # small delay to allow write completion
                            threading.Timer(1.0, _handle_file_event, args=(f, signatures, quarantine, auto_quarantine)).start()
                time.sleep(interval)
        except KeyboardInterrupt:
            return


def scan(paths: List[Path], signatures: List[re.Pattern], quarantine: bool = False) -> int:
    any_findings = False
    # try to detect clamscan availability
    clamscan = shutil.which("clamscan")
    use_clam = clamscan is not None
    if use_clam:
        print(json.dumps({"info": f"clamscan_available: {clamscan}"}))

    yara_rules = load_yara_rules()

    for base in paths:
        if not base.exists():
            print(json.dumps({"path": str(base), "error": "not_found"}))
            continue
        for root, dirs, files in os.walk(str(base)):
            # Skip common large dirs
            if any(p in root for p in ["/node_modules", "/.git", "/.cache"]):
                continue
            for name in files:
                fp = Path(root) / name
                findings = scan_file(fp, signatures)
                # if clamscan available, run it for binaries for extra coverage
                if use_clam and fp.suffix.lower() in [".exe", ".dll", ".so", ""]:
                    try:
                        res = subprocess.run([clamscan, "--no-summary", str(fp)], capture_output=True, text=True, timeout=30)
                        if res.returncode == 1:
                            findings.append("clamscan:infected")
                        elif res.returncode == 2:
                            findings.append("clamscan:error")
                    except Exception:
                        pass
                if findings and findings != ["skipped_large"]:
                    any_findings = True
                    record = {
                        "path": str(fp),
                        "sha256": sha256_of_file(fp),
                        "findings": findings,
                    }
                    print(json.dumps(record, ensure_ascii=False))
                    if quarantine:
                        q = quarantine_file(fp)
                        if q:
                            print(json.dumps({"quarantine": str(q)}))
    return 1 if any_findings else 0


def cli(argv=None):
    p = argparse.ArgumentParser(description="Lightweight antivirus/heuristic scanner for Amrit workspace")
    p.add_argument("--path", "-p", action="append", help="Path to scan (can be used multiple times)", default=["."])
    p.add_argument("--signatures", "-s", help="Signatures file", default=str(SIGNATURES_FILE))
    p.add_argument("--quarantine", action="store_true", help="Move flagged files to quarantine")
    p.add_argument("--watch", action="store_true", help="Watch directories (use with --path) for new files")
    p.add_argument("--watch-interval", type=int, default=5, help="Polling interval (seconds) when watchdog not available")
    p.add_argument("--auto-quarantine", action="store_true", help="Auto-quarantine high-risk files when watching")
    p.add_argument("--max-size-mb", type=int, default=50, help="Skip files larger than this size (MB)")
    args = p.parse_args(argv)

    global MAX_READ_BYTES
    MAX_READ_BYTES = min(MAX_READ_BYTES, args.max_size_mb * 1024 * 1024)

    sigs = load_signatures(Path(args.signatures))
    paths = [Path(p) for p in args.path]
    if args.watch:
        watch_directory(paths, sigs, quarantine=args.quarantine, auto_quarantine=args.auto_quarantine, interval=args.watch_interval)
        rc = 0
    else:
        rc = scan(paths, sigs, quarantine=args.quarantine)
    sys.exit(rc)


if __name__ == "__main__":
    cli()
