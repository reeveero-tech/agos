"""Self-diagnostics runtime (R-F-007).

``diagnostics/__init__.py`` has always imported ``.runtime``, but this module was never
committed, so the ``diagnostics`` package could not be imported. The implementation
lives in ``crossdomain/runtime.py`` (used by ``platform_runtime`` and ``test_platform``).
This module exposes the *same* classes here — one implementation, two addresses — so
both import paths keep working and nothing is duplicated.
"""
from crossdomain.runtime import DiagnosticReport, SelfDiagnosticsRuntime

__all__ = ["SelfDiagnosticsRuntime", "DiagnosticReport"]
