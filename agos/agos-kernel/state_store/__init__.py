"""Importable name for `agos-kernel/state-store` (R-F-004, ADR-0001 §2).

Python cannot import a directory whose name contains '-'. This package makes the code
importable as `state_store` without moving or renaming anything (GOVERNANCE G2): the
hyphenated directory stays the single source of truth, and its `__init__.py` is
loaded here as this module (by the standard ``SourceFileLoader``), with `__path__` pointing at it so submodules resolve.
"""
from pathlib import Path as _AgosPath

__agos_alias_of__ = "state-store"
_agos_src = _AgosPath(__file__).resolve().parent.parent / __agos_alias_of__
__path__ = [str(_agos_src)]
__file__ = str(_agos_src / "__init__.py")
# R-Q-009: executed through the standard import machinery (no ``exec``/``compile``).
import importlib.machinery as _agos_machinery
import sys as _agos_sys
_agos_machinery.SourceFileLoader(__name__, __file__).exec_module(_agos_sys.modules[__name__])
