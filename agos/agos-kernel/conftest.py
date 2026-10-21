"""pytest integration for the kernel's validation scripts (R-F-008).

Some kernel test modules are dual-use scripts: each ``test_*`` function *returns*
``True``/``False`` and ``main()`` prints a verdict. pytest ignores return values (it only
warns), so a function returning ``False`` would be reported as **passed** — a silent lie.

For the modules in ``STRICT_RETURN_MODULES`` this hook runs the function itself and fails
the test when it returns ``False``. The scripts are not modified (GOVERNANCE G2).
R-Q-001 extends the list to every script-style module (and converts them to asserts).

Functions in ``NETWORK_FUNCTIONS`` need the public GitHub repository they name; when it
cannot be reached they are *skipped with an explicit reason* (counted, never hidden).
"""
from __future__ import annotations

import inspect
import subprocess
from functools import lru_cache

import pytest

STRICT_RETURN_MODULES = {"test_validation"}

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


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    module = pyfuncitem.module.__name__.rsplit(".", 1)[-1]
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
