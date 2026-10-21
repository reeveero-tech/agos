"""AGOS Autonomous Engineering Core."""
from .autonomous import AutonomousCore, CoreStatus, Mission, MissionStatus, get_core

__all__ = ["AutonomousCore", "CoreStatus", "Mission", "MissionStatus", "get_core"]


# R-F-008: kernel facade. Resolved lazily so importing ``core`` stays light and the boot
# chain (agos_runtime → bootstrapper → …) is only loaded when the facade is used.
_KERNEL_EXPORTS = ("AGOSKernel", "KernelState", "MissionManager", "MissionResult", "KernelNotRunning")
__all__ += list(_KERNEL_EXPORTS)


def __getattr__(name):
    if name in _KERNEL_EXPORTS:
        from . import kernel as _kernel
        return getattr(_kernel, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
