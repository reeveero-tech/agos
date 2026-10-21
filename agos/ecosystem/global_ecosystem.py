"""Importable name for ``ecosystem/global.py`` (R-F-005).

``global`` is a Python keyword, so ``import ecosystem.global`` / ``from .global import``
are syntax errors and the module was reachable only through ``importlib``. This alias
makes it importable as ``ecosystem.global_ecosystem`` (or ``agos.ecosystem.global_ecosystem``)
without renaming the original file (GOVERNANCE G2). It is the *same module object*:
this module replaces itself in ``sys.modules`` with the real one.
"""
import importlib as _importlib
import sys as _sys

_real = _importlib.import_module((__package__ or "ecosystem") + ".global")
_sys.modules[__name__] = _real
