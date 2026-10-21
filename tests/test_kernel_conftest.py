"""The kernel conftest hooks make script-style tests honest (R-F-008, R-F-010)."""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


def pytest_in(tmp_path: Path, name: str, body: str) -> str:
    shutil.copy(KERNEL / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / name).write_text(body)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    return r.stdout


def test_failure_marker_fails_the_test(tmp_path):
    out = pytest_in(tmp_path, "test_intelligence.py",
                    "def test_ok():\n    print('✓ fine')\n\n"
                    "def test_bad():\n    print('✗ Code analysis failed')\n")
    assert "1 failed, 1 passed" in out, out[-1500:]
    assert "reported failure: ✗ Code analysis failed" in out


def test_script_fixture_uses_the_declared_producer_once_per_module(tmp_path):
    out = pytest_in(tmp_path, "test_runtime.py",
                    "CALLS = []\n"
                    "def test_workspace():\n    CALLS.append(1)\n    return {'id': len(CALLS)}\n\n"
                    "def test_a(platform):\n    assert platform['id'] >= 1\n\n"
                    "def test_b(platform):\n    assert len(CALLS) == 2  # own test run + one fixture build\n")
    assert "3 passed" in out, out[-1500:]
