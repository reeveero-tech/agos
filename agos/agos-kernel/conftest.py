"""pytest integration for the kernel's validation scripts (R-F-008).

Some kernel test modules are dual-use scripts: each ``test_*`` function *returns*
``True``/``False`` and ``main()`` prints a verdict. pytest ignores return values (it only
warns), so a function returning ``False`` would be reported as **passed** — a silent lie.

For the modules in ``STRICT_RETURN_MODULES`` this hook runs the function itself and fails
the test when it returns ``False``. The scripts are not modified (GOVERNANCE G2).

R-Q-001: كل ملفات السكربتات صارت تحمل تأكيدات فعلية داخلها (أداة الإنفاذ:
``tools/quality/assert_audit.py``) — هذه الخطوط آليات احتياطية تبقى لا بديلاً عن التأكيد.

Script fixtures (R-F-010): some scripts chain their checks — ``main()`` calls a
*producer* (e.g. ``platform = test_workspace()``) and passes its result to the other
functions (``test_session(platform)``). ``SCRIPT_FIXTURES`` declares those producers; the
fixtures below call the very same function once per module, exactly as ``main()`` does.

Failure markers (R-F-010): modules in ``FAILURE_MARKER_MODULES`` report a failed check by
printing a line starting with ``✗`` instead of raising; such a line fails the test.

Functions in ``NETWORK_FUNCTIONS`` need the public GitHub repository they name; when it
cannot be reached they are *skipped with an explicit reason* (counted, never hidden).
"""
from __future__ import annotations

import contextlib
import inspect
import io
import subprocess
import sys
from functools import lru_cache

import pytest

STRICT_RETURN_MODULES = {"test_validation"}

FAILURE_MARKER = "✗"
FAILURE_MARKER_MODULES = {"test_runtime", "test_intelligence"}

SCRIPT_FIXTURES = {
    "test_runtime": {"platform": "test_workspace"},
    "test_intelligence": {"report": "test_repository_analysis"},
}

NETWORK_FUNCTIONS = {
    "test_validation": {
        "test_mission_execution": "https://github.com/All-Hands-AI/OpenHands",
        "test_repository_analysis": "https://github.com/All-Hands-AI/OpenHands",
        "test_stress": "https://github.com/All-Hands-AI/OpenHands",
    },
}


@lru_cache(maxsize=None)
def _reachable(url: str) -> bool:
    try:
        return subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True,
                              timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _module_key(module) -> str:
    return module.__name__.rsplit(".", 1)[-1]


def _script_fixture(request, name: str):
    key = _module_key(request.module)
    producer = SCRIPT_FIXTURES.get(key, {}).get(name)
    if producer is None:
        raise LookupError(f"no script producer declared for fixture {name!r} in {key}")
    return getattr(request.module, producer)()


@pytest.fixture(scope="module")
def platform(request):
    """``test_runtime``: the ``UniversalRuntimePlatform`` built by ``test_workspace()``."""
    return _script_fixture(request, "platform")


@pytest.fixture(scope="module")
def report(request):
    """``test_intelligence``: the analysis report built by ``test_repository_analysis()``."""
    return _script_fixture(request, "report")


class _Tee(io.TextIOBase):
    def __init__(self, target):
        self.target, self.buffer = target, io.StringIO()

    def write(self, text):
        self.buffer.write(text)
        return self.target.write(text)

    def flush(self):
        self.target.flush()


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    module = _module_key(pyfuncitem.module)
    if module in FAILURE_MARKER_MODULES and not inspect.iscoroutinefunction(pyfuncitem.obj):
        names = pyfuncitem._fixtureinfo.argnames
        tee = _Tee(sys.stdout)
        with contextlib.redirect_stdout(tee):
            pyfuncitem.obj(**{name: pyfuncitem.funcargs[name] for name in names})
        failed = [line.strip() for line in tee.buffer.getvalue().splitlines()
                  if line.strip().startswith(FAILURE_MARKER)]
        if failed:
            pytest.fail(f"{module}.{pyfuncitem.name} reported failure: " + " | ".join(failed),
                        pytrace=False)
        return True
    if module not in STRICT_RETURN_MODULES:
        return None
    func = pyfuncitem.obj
    if inspect.iscoroutinefunction(func):
        return None  # left to pytest-asyncio
    url = NETWORK_FUNCTIONS.get(module, {}).get(pyfuncitem.name)
    if url and not _reachable(url):
        pytest.skip(f"network: {url} is not reachable")
    names = pyfuncitem._fixtureinfo.argnames
    outcome = func(**{name: pyfuncitem.funcargs[name] for name in names})
    if outcome is False:
        pytest.fail(f"{module}.{pyfuncitem.name} returned False (validation check failed)",
                    pytrace=False)
    return True
