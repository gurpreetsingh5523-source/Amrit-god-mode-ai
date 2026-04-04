"""workspace.tools package helpers and re-exports.

This file re-exports the SelfCodeGenerator class so callers can do
`from workspace.tools import SelfCodeGenerator`.
"""
import sys as _sys, os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

try:
    from workspace.tools.self_code_generator import SelfCodeGenerator
except Exception:
    try:
        from self_code_generator import SelfCodeGenerator  # type: ignore
    except Exception:
        SelfCodeGenerator = None  # type: ignore

__all__ = ["SelfCodeGenerator"]
