"""Forwarding package for ``agos_kernel`` when ``agos/agos-kernel`` is on ``sys.path``.

The single implementation lives in ``agos/agos_kernel/__init__.py`` (R-F-003, ADR-0001);
this file executes it in place so either location yields identical behaviour.
"""
from pathlib import Path as _P

_impl = _P(__file__).resolve().parents[2] / "agos_kernel" / "__init__.py"
__file__ = str(_impl)
exec(compile(_impl.read_text(encoding="utf-8"), str(_impl), "exec"))  # noqa: S102 - trusted repo file
