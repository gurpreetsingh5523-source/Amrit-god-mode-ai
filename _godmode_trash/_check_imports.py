import sys
import os
sys.path.insert(0, '.')
mods = sorted([f[:-3] for f in os.listdir('.') if f.endswith('.py') and f not in ('main.py', '_check_imports.py')])
fails = []
for mod in mods:
    try:
        __import__(mod)
    except Exception as e:
        fails.append((mod, type(e).__name__, str(e)))
        print(f"FAIL {mod}: {type(e).__name__}: {e}")
print(f"\n=== {len(fails)} failures out of {len(mods)} modules ===")
