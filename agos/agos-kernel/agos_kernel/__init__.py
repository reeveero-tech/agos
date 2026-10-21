"""Forwarding package for ``agos_kernel`` when ``agos/agos-kernel`` is on ``sys.path``.

The single implementation lives in ``agos/agos_kernel/__init__.py`` (R-F-003, ADR-0001);
this file loads it in place so either location yields identical behaviour.
"""
from pathlib import Path as _P

_impl = _P(__file__).resolve().parents[2] / "agos_kernel" / "__init__.py"
__file__ = str(_impl)
# R-Q-009: executed through the standard import machinery (no ``exec``/``compile``).
import importlib.machinery as _agos_machinery
import sys as _agos_sys
_agos_machinery.SourceFileLoader(__name__, str(_impl)).exec_module(_agos_sys.modules[__name__])
