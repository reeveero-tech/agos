"""Canaries for the AST scanners behind the kernel golden tests (R-Q-009).

Each scanner must flag the real pattern (including every variant the old text matcher
caught as real code, and variants it missed) and must not flag the known false
positives. If a scanner is ever weakened, these fail.
"""
import ast
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "agos_security_scan", REPO / "agos/agos-kernel/core/tests/security_scan.py")
scan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan  # dataclasses resolve their module through sys.modules
spec.loader.exec_module(scan)

P = Path("sample.py")


def hits(fn, code, *args):
    return fn(P, ast.parse(code), *args)


# -- eval / exec ----------------------------------------------------------------------
@pytest.mark.parametrize("code", [
    "eval(user_input)", "x = eval (data)", "import builtins\nbuiltins.eval(s)",
    "getattr(builtins, 'eval')(s)", "def f():\n    return eval(x)",
])
def test_eval_calls_are_caught(code):
    assert hits(scan.find_dynamic_code_calls, code, ["eval"])


@pytest.mark.parametrize("code", [
    "exec(code)", "exec(compile(src, 'f', 'exec'))", "builtins.exec(s)",
])
def test_exec_calls_are_caught(code):
    assert hits(scan.find_dynamic_code_calls, code, ["exec"])


@pytest.mark.parametrize("code", [
    "if 'eval(' in content: pass", "SAMPLE = {'code': 'eval(user_input)'}",
    "ast.literal_eval(s)", "retrieval(x)", "self.evaluate(x)", "loader.exec_module(m)",
])
def test_eval_exec_false_positives_are_not_flagged(code):
    assert not hits(scan.find_dynamic_code_calls, code, ["eval", "exec"])


# -- secrets ------------------------------------------------------------------------------
@pytest.mark.parametrize("code", [
    "password = 'hunter2'", "API_KEY = 'sk-live-abc123'", "self.token = 'ghp_realtoken'",
    "client(api_key='sk-123456')", "cfg = {'password': 'p4ss'}", "db_password: str = 'x9'",
    "PRIVATE_KEY = '-----BEGIN'", "github_token = 'abc'",
])
def test_secrets_are_caught(code):
    assert hits(scan.find_hardcoded_secrets, code)


@pytest.mark.parametrize("code", [
    "API_KEY = 'api_key'", "TOKEN = 'token'", "client(api_key='test-key')",
    "GitHub(token='test')", "password = 'your_password_here'", "api_key = ''",
    "SAMPLE = {'code': \"password = '123456'\"}", "token = os.environ['TOKEN']",
    "password = '${DB_PASSWORD}'", "secret = 'changeme'",
])
def test_secret_false_positives_are_not_flagged(code):
    assert not hits(scan.find_hardcoded_secrets, code)


# -- SQL --------------------------------------------------------------------------------------
@pytest.mark.parametrize("code", [
    "q = f'SELECT * FROM users WHERE id = {uid}'", "q = 'SELECT name FROM t WHERE a = %s' % a",
    "q = 'DELETE FROM t WHERE id = {}'.format(i)", "q = 'INSERT INTO t VALUES (' + v + ')'",
    "q = f'update accounts set balance = {b}'", "q = f'DROP TABLE {name}'",
])
def test_sql_building_is_caught(code):
    assert hits(scan.find_sql_string_building, code)


@pytest.mark.parametrize("code", [
    "print(f'OK Selected: {x}')", "print(f'State updated to version {v}')",
    "q = 'SELECT * FROM users WHERE id = ?'", "cursor.execute('SELECT 1 FROM t WHERE a = ?', (a,))",
])
def test_sql_false_positives_are_not_flagged(code):
    assert not hits(scan.find_sql_string_building, code)


# -- dynamic imports -----------------------------------------------------------------------
@pytest.mark.parametrize("code", [
    "importlib.import_module(name)", "__import__(request.args['m'])",
    "def load(n):\n    return importlib.import_module(n)", "importlib.import_module(f'{pkg}.x')",
    "from importlib import import_module\nimport_module(user)",
    "mods = get_list()\nfor m in mods:\n    importlib.import_module(m)",
])
def test_unconfined_dynamic_imports_are_caught(code):
    assert hits(scan.find_unsafe_dynamic_imports, code)


@pytest.mark.parametrize("code", [
    "importlib.import_module('providers')",
    "__import__('providers.infrastructure', fromlist=['X'])",
    "def f(name):\n    module_name = f'capabilities.{name}'\n    importlib.import_module(module_name)",
    "modules = ['a', 'b.c']\nfor m in modules:\n    importlib.import_module(m)",
    "def g():\n    for m in ('x', 'y'):\n        importlib.import_module(m)",
])
def test_confined_dynamic_imports_are_allowed(code):
    assert not hits(scan.find_unsafe_dynamic_imports, code)


# -- dependencies ------------------------------------------------------------------------
def test_undeclared_imports_are_caught_and_declared_ones_allowed():
    allowed = scan.allowed_import_roots(REPO)
    assert {"inspect", "io", "subprocess", "asyncio", "requests", "yaml", "psutil", "pytest",
            "agos_kernel", "capabilities", "event_engine"} <= allowed
    assert hits(scan.find_undeclared_imports, "import leftpad_unknown", allowed)
    assert hits(scan.find_undeclared_imports, "from leftpad_unknown import x", allowed)
    assert not hits(scan.find_undeclared_imports, "import inspect, io\nfrom requests import get", allowed)
    guarded = "try:\n    import leftpad_unknown\nexcept ImportError:\n    leftpad_unknown = None"
    assert not hits(scan.find_undeclared_imports, guarded, allowed)
