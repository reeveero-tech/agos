"""Importable name for `agos-kernel/execution-context` (R-F-004, ADR-0001 §2).

Python cannot import a directory whose name contains '-'. This package makes the code
importable as `execution_context` without moving or renaming anything (GOVERNANCE G2): the
hyphenated directory stays the single source of truth, and its `__init__.py` is
executed here as this module, with `__path__` pointing at it so submodules resolve.
"""
from pathlib import Path as _AgosPath

__agos_alias_of__ = "execution-context"
_agos_src = _AgosPath(__file__).resolve().parent.parent / __agos_alias_of__
__path__ = [str(_agos_src)]
__file__ = str(_agos_src / "__init__.py")
exec(compile(_AgosPath(__file__).read_text(encoding="utf-8"), __file__, "exec"))  # noqa: S102 - trusted repo file
