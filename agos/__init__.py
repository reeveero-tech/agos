"""agos — the unified namespace of the AGOS platform (R-F-005, ADR-0001 §3).

The repository has three historical import roots (``agos/agos-kernel``, ``agos/`` and
``agos/rie``) and nine package names that exist in both the kernel and ``agos/``
(civilization, ecosystem, enterprise, evolution, execution, governance, intelligence,
observatory, sdk). This package resolves that **by addition only** (GOVERNANCE G2):

* ``agos.<name>``   — every platform package under ``agos/`` (cognitive, fabric, cloud, ...).
* ``agos.kernel``   — the kernel (directory ``agos/agos-kernel``), same objects as
  ``agos_kernel`` and as the kernel's bare top-level modules (R-F-003).

Collisions disappear because platform packages are always addressed with the ``agos.``
prefix and the kernel with ``agos.kernel`` / ``agos_kernel``.

Single module identity is preserved in every direction:

* ``agos.kernel.X``     is ``agos_kernel.X`` (is the kernel's bare ``X`` when unshadowed).
* ``agos.<name>.Y``     is the bare ``<name>.Y`` if that was already imported from
  ``agos/<name>`` (legacy scripts put ``agos/`` on ``sys.path``), and vice versa: once
  ``agos.<name>`` is loaded, a later bare ``import <name>`` returns the same object —
  except for the nine colliding names, whose bare form keeps meaning the kernel package.

Usage (from the repository root, or once installed — R-F-001)::

    import agos
    from agos.kernel.bootstrapper import Bootstrapper
    from agos.cognitive import ...
    agos.platform_packages()  # -> sorted list of agos.<name> packages
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

__version__ = "0.1.0.dev0"

AGOS_DIR = Path(__file__).resolve().parent
KERNEL_DIR = AGOS_DIR / "agos-kernel"

# Names that exist both in agos/ and in agos/agos-kernel/ (see docs/audit).
COLLIDING_NAMES = frozenset({
    "civilization", "ecosystem", "enterprise", "evolution", "execution",
    "governance", "intelligence", "observatory", "sdk",
})

# agos.<alias> -> canonical absolute module name
_KERNEL_ALIASES = {"kernel": "agos_kernel", "agos_kernel": "agos_kernel"}


def _ensure_agos_kernel():
    """Import the kernel alias package from agos/agos_kernel (R-F-003)."""
    if "agos_kernel" in sys.modules:
        return sys.modules["agos_kernel"]
    spec = importlib.util.spec_from_file_location(
        "agos_kernel", AGOS_DIR / "agos_kernel" / "__init__.py",
        submodule_search_locations=[str(KERNEL_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["agos_kernel"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop("agos_kernel", None)
        raise
    return module


def _under(path_like, root: Path) -> bool:
    try:
        return Path(path_like).resolve().is_relative_to(root.resolve())
    except (OSError, ValueError, TypeError):
        return False


def _is_platform_module(module, top: str) -> bool:
    """True if ``module`` was loaded from agos/<top> (not from the kernel)."""
    locs = list(getattr(module, "__path__", []) or [])
    f = getattr(module, "__file__", None)
    if f:
        locs.append(f)
    root = AGOS_DIR / top
    return bool(locs) and all(_under(p, root) for p in locs)


def platform_packages() -> list[str]:
    """Every importable platform package directly under agos/ (excluding the kernel)."""
    out = []
    for d in sorted(AGOS_DIR.iterdir()):
        if d.is_dir() and d.name.isidentifier() and d.name != "agos_kernel" \
                and (d / "__init__.py").is_file():
            out.append(d.name)
    return out


class _AliasLoader(importlib.abc.Loader):
    """Return an already-importable module object under a second name (same object)."""

    def __init__(self, real: str):
        self.real = real

    def create_module(self, spec):
        return importlib.import_module(self.real)

    def exec_module(self, module):
        """Already executed under its canonical name; record the alias."""
        aliases = getattr(module, "__agos_aliases__", None)
        if not isinstance(aliases, set):
            try:
                module.__agos_aliases__ = aliases = set()
            except (AttributeError, TypeError):
                return
        aliases.add(self.real)


def _alias_spec(fullname: str, real: str):
    target = sys.modules.get(real)
    if target is not None:
        is_pkg = hasattr(target, "__path__")
    else:
        found = importlib.util.find_spec(real)
        if found is None:
            return None
        is_pkg = found.submodule_search_locations is not None
    loader = _AliasLoader(real)
    return importlib.machinery.ModuleSpec(fullname, loader, is_package=is_pkg)


class _AgosNamespaceFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        parts = fullname.split(".")
        # 0) bare agos_kernel (R-F-003) is resolvable once `agos` is imported
        if fullname == "agos_kernel":
            return importlib.util.spec_from_file_location(
                "agos_kernel", AGOS_DIR / "agos_kernel" / "__init__.py",
                submodule_search_locations=[str(KERNEL_DIR)])
        # 1) agos.kernel[.X...] / agos.agos_kernel[.X...] -> agos_kernel[.X...]
        if parts[0] == "agos" and len(parts) >= 2 and parts[1] in _KERNEL_ALIASES:
            _ensure_agos_kernel()
            real = ".".join([_KERNEL_ALIASES[parts[1]], *parts[2:]])
            return _alias_spec(fullname, real)
        # 2) agos.<name>[...] -> bare <name>[...] if that was already loaded from agos/<name>
        if parts[0] == "agos" and len(parts) >= 2:
            bare = ".".join(parts[1:])
            m = sys.modules.get(bare)
            if m is not None and _is_platform_module(m, parts[1]):
                return _alias_spec(fullname, bare)
            return None  # normal load as agos.<name> from agos/<name>
        # 3) bare <name>[...] -> agos.<name>[...] once the namespaced one is loaded
        if parts[0] not in COLLIDING_NAMES and parts[0] not in ("agos", "agos_kernel"):
            namespaced = "agos." + fullname
            m = sys.modules.get(namespaced)
            if m is not None and _is_platform_module(m, parts[0]):
                return _alias_spec(fullname, namespaced)
        return None


def _install() -> None:
    if not any(type(f).__name__ == "_AgosNamespaceFinder" for f in sys.meta_path):
        sys.meta_path.insert(0, _AgosNamespaceFinder())


_install()

__all__ = ["AGOS_DIR", "KERNEL_DIR", "COLLIDING_NAMES", "platform_packages", "__version__"]
