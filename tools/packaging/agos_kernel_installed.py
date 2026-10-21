"""Installed top-level ``agos_kernel`` (R-F-001) — shipped in the wheel as agos_kernel/__init__.py.

Executes the single implementation ``agos/agos_kernel/__init__.py`` of the installed
``agos`` package in place (loaded by the standard ``SourceFileLoader``) (same pattern as agos/agos-kernel/agos_kernel), so there is one
source of truth for the kernel alias (R-F-003, ADR-0001).
"""
import importlib.util as _ilu
from pathlib import Path as _P

_spec = _ilu.find_spec("agos")
_impl = _P(next(iter(_spec.submodule_search_locations))) / "agos_kernel" / "__init__.py"
__file__ = str(_impl)
# R-Q-009: executed through the standard import machinery (no ``exec``/``compile``).
import importlib.machinery as _agos_machinery
import sys as _agos_sys
_agos_machinery.SourceFileLoader(__name__, str(_impl)).exec_module(_agos_sys.modules[__name__])
