"""Shared fixtures for the kernel golden tests (R-F-010).

``kernel_dir`` was defined only inside some test classes (e.g. ``TestKernelSecurity``),
so tests in other classes that request it (``TestSecurityBestPractices``) errored with
"fixture 'kernel_dir' not found". This module-level fixture provides the same value; the
class-level definitions keep precedence where they exist.
"""
import os
from pathlib import Path

import pytest

_AGOS_ROOT = Path(os.environ.get("AGOS_ROOT") or Path(__file__).resolve().parents[3])
_AGOS_KERNEL = _AGOS_ROOT / "agos-kernel"


@pytest.fixture
def kernel_dir() -> Path:
    """The kernel source directory (``agos/agos-kernel``, overridable via ``AGOS_ROOT``)."""
    return Path(str(_AGOS_KERNEL))
