Lightweight Antivirus Scanner

This folder contains a small heuristic scanner intended for quick local checks.

Files:
- `antivirus.py` : CLI scanner. Scans paths for suspicious patterns and can quarantine matches.
- `signatures.txt` : Regex signatures used for detection. Edit to add new patterns observed in suspicious files.
- `quarantine/` : Where flagged files are moved when using `--quarantine`.

Usage examples:

Preview scan (no quarantine):

```
python3 workspace/security/antivirus.py --path .
```

Scan and quarantine:

```
python3 workspace/security/antivirus.py --path . --quarantine
```

Notes and safety:
- This scanner is heuristic and may produce false positives. Review findings before deleting files.
- For a production-grade AV solution, install ClamAV or a commercial AV product.
- Do not run quarantine on system directories unless you understand the consequences.

Additional features (new):

- YARA rules: If the Python `yara` package is installed and `workspace/security/signatures.yar` is present, the scanner will apply YARA rules for better detection.
- ClamAV integration: If `clamscan` is available in PATH the scanner will call it for extra checks (optional).
- Archive scanning: ZIP and TAR archives are inspected (first 256 KiB of each member) without extracting to disk.
- Downloads watcher: Run with `--watch` to monitor `~/Downloads` (or use `--path` for a custom watch target). Requires `watchdog` for efficient watching, otherwise the scanner will fall back to a polling loop.
- Improved quarantine: Quarantined files now include a `.meta.json` sidecar with original path and sha256; a future `--restore` option is supported by the tool.

Recommended workflow after a suspicious download:

1. Do NOT open/run the file.
2. Run a scan on the file or the Downloads folder:

```bash
python3 workspace/security/antivirus.py --path ~/Downloads --quarantine
```

3. Inspect the JSON output lines; if unsure, upload a small sample (not entire binary) and hashes to VirusTotal or consult a trusted analyst.
4. To get stronger coverage, install ClamAV (`brew install clamav`) and optionally `yara` (`pip install yara-python`) and re-run the scan.

If you'd like, I can:
- walk through the top 5 findings you saw and recommend file-specific actions (restore, delete, rebuild venv), or
- automatically quarantine high-confidence findings and prepare venv recreation commands (I will ask before deleting anything).

Watcher / 24x7 protection
--------------------------------

You can run the scanner in watch mode to monitor `~/Downloads` (or any directory) for new files and automatically scan them. Watch mode supports two levels:

- `--quarantine` : any flagged file will be moved to `workspace/security/quarantine/` and recorded in `watch.log`.
- `--auto-quarantine` : when watching, high-confidence findings (YARA, clamscan infected, download-and-exec heuristics, or binary headers) will be auto-quarantined immediately. This is useful for simple 24x7 protection but please note it may quarantine false positives.

Usage (example):

```bash
# monitor Downloads and print findings; do not auto-quarantine
python3 workspace/security/antivirus.py --path ~/Downloads --watch

# monitor Downloads and auto-quarantine high-risk files
python3 workspace/security/antivirus.py --path ~/Downloads --watch --auto-quarantine

# monitor Downloads and quarantine any flagged file (less conservative)
python3 workspace/security/antivirus.py --path ~/Downloads --watch --quarantine
```

Notes:
- The watcher uses the `watchdog` package if available for efficient filesystem events. If `watchdog` is not installed the watcher will poll the directory every `--watch-interval` seconds (default 5s).
- The watcher writes a log to `workspace/security/watch.log`. Quarantined files are moved into `workspace/security/quarantine/` with a sidecar `.meta.json` describing original path and sha256.
- This autoprotecter is helpful for automatically isolating suspicious downloads, but it is not a full replacement for a commercial AV product. Keep backups and review quarantined files regularly.
