"""Import health of packages revived by R-F-007 (``diagnostics``, ``decision``).

Each case runs in a fresh interpreter from the kernel directory (the same way the
kernel's own scripts run), so no ``sys.modules`` state leaks between cases.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"


def run(code: str) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip()


def test_diagnostics_package_imports_and_shares_one_implementation():
    out = run("""
        import diagnostics, diagnostics.runtime as d, crossdomain.runtime as c
        print(d.SelfDiagnosticsRuntime is c.SelfDiagnosticsRuntime,
              d.DiagnosticReport is c.DiagnosticReport)
    """)
    assert out == "True True"


def test_decision_package_imports():
    out = run("""
        import decision
        print(hasattr(decision, "DecisionEngine"))
    """)
    assert out == "True"


def test_result_is_generic_and_backward_compatible():
    out = run("""
        from shared import Result, ResultStatus
        alias = Result[int]
        r = Result(status=ResultStatus.SUCCESS, data=5)
        print(alias.__origin__ is Result, r.data, r.status.value)
    """)
    assert out.startswith("True 5 ")
