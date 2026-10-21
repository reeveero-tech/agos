"""agos_kernel — the importable name of the AGOS kernel (R-F-003, ADR-0001).

The kernel lives in the directory ``agos/agos-kernel`` (a hyphen, which Python cannot
import). Code across the project — notably ``civilization`` and ``core.invariants`` —
imports it as ``agos_kernel.X``. This package makes that work **without moving or
renaming anything** (GOVERNANCE G2), and with a single module identity:

* ``agos_kernel.X`` is the *same module object* as the kernel's top-level ``X``
  (``agos_kernel.core.seal is core.seal``), so classes, registries and singletons are
  never duplicated.
* If the bare name ``X`` is already taken by a different, non-kernel module (one of the
  nine names shared with ``agos/``, e.g. ``civilization``), the kernel module is loaded
  under ``agos_kernel.X`` as its own canonical name instead of shadowing the other one.
  R-F-005 removes that case by moving outer modules under ``agos.*``.

The kernel's own ``__init__`` metadata (``__version__``, ``__phase__``) is re-exported.
Importable from ``agos/`` (scripts insert it on ``sys.path``) and from ``agos/agos-kernel``
(via the forwarding package ``agos/agos-kernel/agos_kernel``).
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

KERNEL_DIR = Path(os.environ.get("AGOS_ROOT") or Path(__file__).resolve().parents[1]) / "agos-kernel"
_PREFIX = __name__ + "."

# The kernel package itself is a regular package: keep its metadata available here.
__version__ = "0.0.0"
__phase__ = None
_kernel_init = KERNEL_DIR / "__init__.py"
if _kernel_init.is_file():
    _meta: dict = {}
    exec(compile(_kernel_init.read_text(encoding="utf-8"), str(_kernel_init), "exec"), _meta)  # noqa: S102 - trusted repo file
    __version__ = _meta.get("__version__", __version__)
    __phase__ = _meta.get("__phase__", __phase__)
    __doc__ = (__doc__ or "") + "\nKernel: " + (_meta.get("__doc__") or "").strip()

# Kernel modules use top-level absolute imports (``from container import ...``).
if str(KERNEL_DIR) not in sys.path:
    sys.path.append(str(KERNEL_DIR))

# Submodules not handled by the alias finder are found inside the kernel directory.
__path__ = [str(KERNEL_DIR)]


def _in_kernel(module) -> bool:
    f = getattr(module, "__file__", None)
    locs = list(getattr(module, "__path__", []) or [])
    paths = ([f] if f else []) + locs
    try:
        return bool(paths) and all(Path(p).resolve().is_relative_to(KERNEL_DIR.resolve()) for p in paths)
    except (OSError, ValueError):
        return False


def _spec_in_kernel(spec) -> bool:
    locs = list(spec.submodule_search_locations or []) + ([spec.origin] if spec.has_location and spec.origin else [])
    try:
        return bool(locs) and all(Path(p).resolve().is_relative_to(KERNEL_DIR.resolve()) for p in locs)
    except (OSError, ValueError):
        return False


def _load_kernel_top(top: str):
    """Import kernel top-level module ``top`` under its bare name, from KERNEL_DIR only."""
    spec = importlib.machinery.PathFinder.find_spec(top, [str(KERNEL_DIR)])
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[top] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(top, None)
        raise
    return module


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, real: str):
        self.real = real

    def create_module(self, spec):
        return importlib.import_module(self.real)

    def exec_module(self, module):
        """Already executed under its real name; record the alias for introspection."""
        aliases = getattr(module, "__agos_aliases__", None)
        if not isinstance(aliases, set):
            try:
                module.__agos_aliases__ = aliases = set()
            except (AttributeError, TypeError):
                return
        aliases.add(_PREFIX + self.real)


class _KernelAliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``agos_kernel.X[.Y...]`` to the kernel module ``X[.Y...]`` (same object)."""

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_PREFIX):
            return None
        real = fullname[len(_PREFIX):]
        top = real.split(".")[0]
        if "." in real:
            alias_top = sys.modules.get(_PREFIX + top)
            if alias_top is None or alias_top is not sys.modules.get(top):
                return None  # parent is a standalone kernel module: normal path lookup
        else:
            existing = sys.modules.get(top)
            if existing is None:
                if importlib.machinery.PathFinder.find_spec(top, [str(KERNEL_DIR)]) is None:
                    return None
                elsewhere = importlib.machinery.PathFinder.find_spec(top)
                if elsewhere is not None and not _spec_in_kernel(elsewhere):
                    return None  # bare name belongs to another module on sys.path: don't shadow it
                _load_kernel_top(top)
            elif not _in_kernel(existing):
                return None  # name collision: load kernel copy under agos_kernel.X itself
        target_mod = sys.modules.get(real)
        is_pkg = hasattr(target_mod, "__path__") if target_mod is not None else \
            bool(importlib.util.find_spec(real) and importlib.util.find_spec(real).submodule_search_locations)
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(real), is_package=is_pkg)
        return spec


def _install() -> None:
    for f in sys.meta_path:
        if type(f).__name__ == "_KernelAliasFinder":
            return
    sys.meta_path.insert(0, _KernelAliasFinder())


_install()

__all__ = ["KERNEL_DIR", "__version__", "__phase__"]
