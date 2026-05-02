"""Small CLI to exercise SelfCodeGenerator.

Usage examples:
  python3 -m workspace.tools.cli generate-module --name sanity_check --code "def ok():\n    print('ok')"
"""
import argparse
import logging
import sys

try:
    from knowledge_store import KnowledgeStore
except Exception:
    # Minimal stub if knowledge_store isn't importable in some contexts
    class KnowledgeStore:  # type: ignore
        def add_knowledge(self, *a, **k):
            return None

import sys as _sys
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

try:
    from workspace.tools.self_code_generator import SelfCodeGenerator
except Exception:
    from self_code_generator import SelfCodeGenerator  # type: ignore


def _build_parser():
    p = argparse.ArgumentParser(description="Workspace tools CLI")
    sub = p.add_subparsers(dest="cmd")

    g = sub.add_parser("generate-module", help="Generate a python module")
    g.add_argument("--name", required=True, help="Module name (filesystem-safe)")
    g.add_argument("--code", required=True, help="Code string to write into module")
    g.add_argument("--out", default="generated", help="Output directory")

    w = sub.add_parser("generate-web", help="Generate a simple web bundle")
    w.add_argument("--name", required=True)
    w.add_argument("--html", required=True)
    w.add_argument("--js", default="")
    w.add_argument("--css", default="")
    w.add_argument("--out", default="generated")

    return p


def main(argv=None):
    logging.basicConfig(level=logging.INFO)
    p = _build_parser()
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 1

    kb = KnowledgeStore()
    gen = SelfCodeGenerator(kb, out_dir=getattr(args, "out", "generated"))

    if args.cmd == "generate-module":
        path = gen.generate_python_module(args.name, args.code)
        print(path)
        return 0
    if args.cmd == "generate-web":
        path = gen.generate_simple_web(args.name, args.html, js=args.js, css=args.css)
        print(path)
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
