"""Aware UTC time instead of the deprecated naive ``datetime.utcnow()`` (R-F-012)."""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"
sys.path.insert(0, str(REPO / "tools" / "migrate"))
import aware_utc  # noqa: E402


def test_no_utcnow_call_site_remains():
    assert aware_utc.remaining() == {}


def test_pytest_turns_a_reintroduced_utcnow_into_an_error():
    import tomllib
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    assert "error:datetime.datetime.utcnow:DeprecationWarning" in cfg["filterwarnings"]


def test_codemod_rewrites_every_form_and_only_code(tmp_path):
    src = textwrap.dedent('''\
        """Docs mention datetime.utcnow() and stay as they are."""
        from dataclasses import dataclass, field
        from datetime import datetime, timedelta
        # comment: datetime.utcnow() stays

        @dataclass
        class A:
            at: datetime = field(default_factory=datetime.utcnow)
            s: str = field(default_factory=lambda: datetime.utcnow().isoformat())

        def f():
            from datetime import datetime
            label = "وقت"; t = datetime.utcnow()
            g = datetime.utcnow
            return f"{datetime.utcnow().isoformat()} {label}", t, g, "datetime.utcnow()"
        ''')
    out, sites = aware_utc.rewrite(src)
    assert sites == 5
    assert "from datetime import datetime, timedelta, timezone" in out
    assert "    from datetime import datetime, timezone" in out           # local import too
    assert "default_factory=lambda: datetime.now(timezone.utc))" in out
    assert 'label = "وقت"; t = datetime.now(timezone.utc)' in out         # byte offsets vs chars
    assert "g = (lambda: datetime.now(timezone.utc))" in out
    assert 'f"{datetime.now(timezone.utc).isoformat()} {label}"' in out   # f-string expression
    assert out.count("datetime.utcnow()") == 3                           # docstring, comment, string
    assert aware_utc.rewrite(out) == (out, 0)                            # idempotent
    import importlib.util
    path = tmp_path / "canary_mod.py"
    path.write_text(out, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("canary_mod", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["canary_mod"] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    stamp, t, g, _ = mod.f()
    assert t.utcoffset().total_seconds() == 0 and g().tzinfo is not None
    assert stamp.split()[0].endswith("+00:00") and mod.A().at.tzinfo is not None


def _in_riyadh(code: str) -> str:
    env = {**os.environ, "TZ": "Asia/Riyadh"}
    r = subprocess.run([sys.executable, "-W", "ignore::DeprecationWarning", "-c", code],
                       cwd=KERNEL, env=env, capture_output=True, text=True, timeout=120, check=True)
    return r.stdout.strip().splitlines()[-1]


def test_trace_duration_is_correct_outside_utc():
    """The bug R-F-012 fixes: a naive UTC time read back with .timestamp() is taken as
    *local* time, so on a UTC+3 host every span lasted three hours."""
    old = float(_in_riyadh(
        "import time; from datetime import datetime\n"
        "start = datetime.utcnow().isoformat()\n"
        "print((time.time() - datetime.fromisoformat(start).timestamp()) * 1000)"))
    assert old > 3 * 3600 * 1000 - 60_000          # the canary: the old formula is 3 h off
    new = float(_in_riyadh(
        "from civilization.telemetry_runtime.telemetry import TracingRuntime\n"
        "rt = TracingRuntime(); span = rt.start_span('op'); rt.end_span(span)\n"
        "print(span.duration_ms)"))
    assert 0 <= new < 60_000


def test_timestamps_are_explicitly_utc():
    out = _in_riyadh(
        "from civilization.telemetry_runtime.telemetry import Metric, TracingRuntime\n"
        "print(Metric().timestamp + ' ' + TracingRuntime().start_span('x').start_time)")
    assert all(s.endswith("+00:00") for s in out.split())
