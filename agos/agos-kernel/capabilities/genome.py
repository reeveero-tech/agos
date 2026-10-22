"""R-W2-012 — CGP: جينوم القدرات من DNA المستودع (Capability Genome Project).

تقرير قدرات لمستودع حقيقي: المهارات (skills) والقدرات (capabilities) المشتقة
من حقائق التحليل الموحد (ADR-0005 — ``capabilities/analysis_service``)، بلا مسح
جديد ولا خط موازٍ: الإسقاط صرف فوق ``SharedAnalysis``.

مبدأ الأمانة في الأدلة (ADR-0002 — سياسات النقص المعلن):
- **statically_supported** تعني «استدعاء مفهوم استاتيكياً في شيفرة إنتاج» — لا
  تعني «مُتحقق منه تشغيلياً» ولا تُعرض كذلك. والنطاق محدود (بيثون AST + وثائق
  CI) فغياب الدليل ليس دليل غياب.
- **declared** تعني «مصرّح به في ملف اعتماديات» فقط — لا استدعاء مفهوم.
- **candidate** قدرة مهاراتها موجودة لكن لا في رمز واحد؛ **declared** قدرة
  مهاراتها مصرّح بها فقط؛ وما عداه **absent** والناقص مسمّى.
- مقاييس الأداء (دقة/كلفة/زمن) **غير مقيسة** فلا تُخترع — تُعلن كفجوة.

محدودية النطاق معلنة لا صامتة: المستخرج يفهم بيثون فقط (AST بنطاقات معجمية
وحل روابط واستيراد وحجب الأسماء المعاد ربطها، والهوية رموز مؤهلة
``Class.method``)، واللغات الأخرى فجوة مسمّاة، والملفات غير المقروءة وأخطاء
المسح وأخطاء التحليل تُعلن بتفاصيلها، لا تُحسب ثم تُفقد.
"""
from __future__ import annotations

import ast
import shlex
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from interfaces import ICapability

__all__ = [
    "build_capability_genome", "CapabilityGenomeCapability",
]

GENOME_SCHEMA_VERSION = "cgp-1.0"
RULES_VERSION = "python-ast-2"


# ---------------------------------------------------------------------------
# فهرس القواعد — استدعاءات مفهومة استاتيكياً (أهداف منقّطة كاملة)
# ---------------------------------------------------------------------------

#: استدعاء ``module.attr(...)`` أو ``from module import attr`` — الهدف المنقط
#: الكامل يطابق قاعدة مهارة. أسماء المستورَد تُحل عبر روابط الاستيراد المعجمية.
_CALL_RULES: Dict[str, Set[str]] = {
    "http_request": {
        "requests.get", "requests.post", "requests.put", "requests.delete",
        "requests.head", "requests.patch", "requests.request",
        "httpx.get", "httpx.post", "httpx.put", "httpx.delete",
        "httpx.patch", "httpx.request",
        "urllib.request.urlopen",
    },
    "parse_json": {
        "json.load", "json.loads", "orjson.loads", "ujson.loads",
    },
    "parse_yaml": {
        "yaml.safe_load", "yaml.load", "ruamel.yaml.YAML",
    },
    "run_command": {
        "subprocess.run", "subprocess.call", "subprocess.check_output",
        "subprocess.check_call", "subprocess.Popen",
        "os.system", "os.popen",
    },
    "git_operations": {
        "git.Repo",   # GitPython
        "sh.git",     # sh
    },
    "run_tests": {
        "pytest.main",
    },
    "parse_cli_args": {
        "argparse.ArgumentParser", "click.command", "click.group",
        "click.option", "click.argument", "typer.Typer", "typer.run",
    },
    "logging": {
        "logging.getLogger", "logging.basicConfig", "logging.config.dictConfig",
    },
}

#: طريقة معروفة على مستقبل معروف: ``pathlib.Path.read_text`` — الاسم المنطوق
#: على أي مستقبل لا يكفي (``x.read_text()`` على مستقبل مجهول ليس دليلاً).
_PATHLIB_METHOD_RULES: Dict[str, Set[str]] = {
    "file_read": {"read_text", "read_bytes"},
    "file_write": {"write_text", "write_bytes"},
}
_PATHLIB_TARGET = "pathlib.Path"

#: استدعاءات صريحة لأوامر git عبر مدير العمليات: أول معامل قائمة تبدأ بـ "git"
#: أو سلسلة أمر git.
_GIT_ARG_PREFIX = "git"

#: أوامر اختبار في خطوات CI — مطابقة رموز أمر فعلية (shlex) لا سلاسل جزئية:
#: ``pip install pytest`` و``echo pytest`` لا يُحسبان تشغيلاً للاختبارات.
_CI_TEST_COMMANDS: Dict[str, Tuple[Tuple[str, ...], ...]] = {
    "pytest": (("pytest",), ("python", "-m", "pytest"),
               ("python3", "-m", "pytest")),
    "npm": (("npm", "test"), ("npm", "run", "test"),
            ("yarn", "test"), ("pnpm", "test")),
    "go": (("go", "test"),),
    "cargo": (("cargo", "test"),),
    "mvn": (("mvn", "test"),),
    "gradle": (("gradle", "test"),),
    "tox": (("tox",),),
    "nox": (("nox",),),
}

#: اعتمادية مصرّح بها في ملف اعتماديات ⇒ دليل «declared» لمهارة (لا أكثر).
_DECLARED_DEP_SKILLS: Dict[str, str] = {
    "requests": "http_request", "httpx": "http_request", "aiohttp": "http_request",
    "urllib3": "http_request", "pycurl": "http_request",
    "pyyaml": "parse_yaml", "ruamel-yaml": "parse_yaml", "ruamel.yaml": "parse_yaml",
    "orjson": "parse_json", "ujson": "parse_json",
    "pytest": "run_tests", "tox": "run_tests", "nox": "run_tests",
    "gitpython": "git_operations", "dulwich": "git_operations",
    "click": "parse_cli_args", "typer": "parse_cli_args",
}

#: القدرات: تركيبات مهارات — لا تُعلن verified إلا بتركيب موثق في رمز واحد.
_CAPABILITY_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "TestExecution": ("run_tests",),
    "GitAutomation": ("git_operations",),
    "CommandLineTool": ("parse_cli_args",),
    "HttpJsonClient": ("http_request", "parse_json"),
    "FileTransform": ("file_read", "file_write"),
}

_SKILL_CATEGORIES: Dict[str, str] = {
    "http_request": "web", "parse_json": "data", "parse_yaml": "data",
    "run_command": "execution", "git_operations": "vcs", "run_tests": "testing",
    "parse_cli_args": "cli", "logging": "observability",
    "file_read": "file-operations", "file_write": "file-operations",
}

_CODE_EXTENSIONS = {".py"}
_PYTHON_LANGUAGE_KEYS = {"python", "python3"}
_SUBPROCESS_TARGETS = (
    "subprocess.run", "subprocess.call", "subprocess.check_output",
    "subprocess.check_call", "subprocess.Popen", "os.system", "os.popen")


def _is_test_path(path: str) -> bool:
    """سياق الملف: اختبار/مثال أم إنتاج — يعزل أدلة الاختبار عن دليل الإنتاج."""
    parts = path.replace("\\", "/").lower().split("/")
    base = parts[-1] if parts else ""
    return ("tests" in parts or "test" in parts
            or base.startswith("test_") or base.endswith("_test.py"))


def _target_names(target: ast.AST) -> Set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    out: Set[str] = set()
    for child in ast.iter_child_nodes(target):
        out.update(_target_names(child))
    return out


def _direct_scope_facts(body: List[ast.stmt]) -> Tuple[Dict[str, str], Set[str]]:
    """روابط الاستيراد والأسماء المُعاد ربطها في نطاق واحد — بلا النزول إلى
    الدوال/الأصناف المتداخلة (نطاقها المستقل يحسب عند زيارته).

    الاسم المستورَد في دالة لا يصير رابطاً في دالة أخرى، والاسم المُسند في نطاق
    يحجب الاستيراد في ذلك النطاق وما تحته فقط.
    """
    bindings: Dict[str, str] = {}
    assigned: Set[str] = set()
    for stmt in body:
        for n in _walk_non_nested(stmt):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    top = alias.name.split(".")[0]
                    # بلا اسم مستعار: الرابط الحزمة العليا (import urllib.request
                    # يربط urllib ⇒ urllib.request.urlopen يُحل صحيحاً)؛ وباسم
                    # مستعار: الهدف المنقط كاملاً (import urllib.request as req
                    # يربط req ⇒ urllib.request ⇒ req.urlopen يُحل urlopen منه)
                    bindings[alias.asname or top] = alias.name if alias.asname else top
            elif isinstance(n, ast.ImportFrom):
                if n.module is None or n.level:  # نسبي — غير مفهوم
                    continue
                for alias in n.names:
                    if alias.name == "*":
                        continue
                    bindings[alias.asname or alias.name] = f"{n.module}.{alias.name}"
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    assigned.update(_target_names(t))
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                if n.target is not None:
                    assigned.update(_target_names(n.target))
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef)):
                assigned.add(n.name)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                assigned.add(n.name)
            elif isinstance(n, ast.Global):
                assigned.update(n.names)
    return bindings, assigned


class _ModuleFacts:
    """حقائق وحدة واحدة: استدعاءات مهارة بأدلتها + أخطاء التحليل إن وجدت."""

    def __init__(self, path: str):
        self.path = path
        #: (skill, line, symbol, rule, context)
        self.findings: List[Tuple[str, int, str, str, str]] = []
        self.parse_error: Optional[str] = None


def _analyze_python(path: str, text: str) -> _ModuleFacts:
    facts = _ModuleFacts(path)
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        facts.parse_error = f"{type(exc).__name__}: line {exc.lineno}"
        return facts
    context = "test" if _is_test_path(path) else "production"
    _visit_scope(tree.body, [], {}, set(), facts, context)
    return facts


def _visit_scope(body: List[ast.stmt], prefix: List[str],
                 outer_bindings: Dict[str, str], outer_shadowed: Set[str],
                 facts: _ModuleFacts, context: str) -> None:
    """زيارة نطاق واحد (وحدة/دالة/صنف) بروابطه المعجمية ورمزه المؤهل.

    استيرادات النطاق تُضاف فوق روابط النطاقات المحيطة (لا روابط الدوال
    الشقيقة)، والأسماء المُسندة في النطاق تحجب الروابط فيه وفي نطاقاته الداخلية
    فقط، والرمز المؤهل ``Class.method`` فلا تتصادم دالتان بالاسم نفسه،
    والمزخرفات تُحسب بروابط النطاق المحيط لا الداخلي.
    """
    bindings, assigned = _direct_scope_facts(body)
    bindings = {**outer_bindings, **bindings}
    shadowed = outer_shadowed | assigned
    symbol = ".".join(prefix) if prefix else "<module>"

    for stmt in body:
        if isinstance(stmt, ast.ClassDef):
            # نطاق الصنف ليس نطاقاً معجمياً لطرقه: الروابط داخل جسم الصنف
            # لا تراها الطرق (وإلا صار استيراد جسم صنف دليلاً لطريقة لا تراه
            # وقت التشغيل) — الطرق ترث روابط النطاق المحيط فقط
            class_bindings, class_assigned = _direct_scope_facts(stmt.body)
            merged_class = {**bindings, **class_bindings}
            class_shadowed = shadowed | class_assigned
            for sub in stmt.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    inner_shadow = set(shadowed) | _param_names(sub)
                    _visit_scope(sub.body, prefix + [stmt.name, sub.name],
                                 bindings, inner_shadow, facts, context)
                else:
                    for n in _walk_non_nested(sub):
                        if isinstance(n, ast.Call):
                            _record_call(facts, n, merged_class, class_shadowed,
                                         ".".join(prefix + [stmt.name]), context)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # المزخرفات والقيم الافتراضية: نطاق المحيط لا النطاق الداخلي
            for dec in getattr(stmt, "decorator_list", []) or []:
                for n in _walk_non_nested(dec):
                    if isinstance(n, ast.Call):
                        _record_call(facts, n, bindings, shadowed, symbol, context)
            inner_shadow = set(shadowed)
            if hasattr(stmt, "args"):
                inner_shadow |= _param_names(stmt)
            _visit_scope(stmt.body, prefix + [stmt.name], bindings,
                         inner_shadow, facts, context)
        else:
            for n in _walk_non_nested(stmt):
                if isinstance(n, ast.Call):
                    _record_call(facts, n, bindings, shadowed, symbol, context)


def _walk_non_nested(root: ast.AST):
    """السير بلا نزول إلى الدوال/الأصناف — جسم الدالة نطاق مستقل يُزار وحده
    بروابطه الخاصة، فلا تُحسب استدعاءات دالة على روابط دالة شقيقة، ولا
    استيراد محلي لدالة كأنه رابط على مستوى الوحدة."""
    stack: List[ast.AST] = [root]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            continue  # النطاق الداخلي يُزار وحده
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                stack.append(child)  # الرمز نفسه يُرى كاسم مُسند فقط
            else:
                stack.append(child)


def _param_names(func: ast.AST) -> Set[str]:
    a = func.args  # type: ignore[attr-defined]
    names = {arg.arg for arg in list(a.posonlyargs) + list(a.args)
             + list(a.kwonlyargs)}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def _dotted_target(node: ast.AST, bindings: Dict[str, str],
                   shadowed: Optional[Set[str]] = None) -> Optional[str]:
    """الهدف المنقط للاستدعاء إن كان مفهوماً: اسم مربوط باستيراد + سلسلة صفات،
    أو اسماً مستورَداً مباشرة. غير المفهوم يُرجع None — لا يُخمَّن. والاسم
    الجذري المعاد ربطه يحجب السلسلة كلها (urllib = None ثم urllib.request…)."""
    parts: List[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    if shadowed is not None and cur.id in shadowed:
        return None
    bound = bindings.get(cur.id)
    if bound is None:
        return None
    parts.append(bound)
    return ".".join(reversed(parts))


def _first_arg_string(node: ast.Call) -> Optional[ast.AST]:
    if node.args:
        return node.args[0]
    for kw in node.keywords:
        if kw.arg in ("args", "cmd", "command"):
            return kw.value
    return None


def _git_arg_evidence(node: ast.Call) -> bool:
    """استدعاء مدير عمليات بأمر git صريح: قائمة تبدأ بـ "git" أو سلسلة أمر git."""
    arg = _first_arg_string(node)
    if arg is None:
        return False
    if isinstance(arg, ast.List) and arg.elts:
        first = arg.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value == _GIT_ARG_PREFIX
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return (arg.value == _GIT_ARG_PREFIX
                or arg.value.startswith(_GIT_ARG_PREFIX + " "))
    return False


def _open_mode(node: ast.Call) -> Optional[str]:
    """وضع open() إن كان ثابتاً معروفاً؛ الوضع الديناميكي غير محسوم فلا دليل."""
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str):
            return kw.value.value
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
            and isinstance(node.args[1].value, str):
        return node.args[1].value
    if len(node.args) < 2 and not any(kw.arg == "mode" for kw in node.keywords):
        return ""  # بلا معامل mode ⇒ القراءة الافتراضية الموثقة
    return None


def _record_call(facts: _ModuleFacts, call: ast.Call,
                 bindings: Dict[str, str], shadowed: Set[str], symbol: str,
                 context: str) -> None:
    func = call.func
    line = getattr(call, "lineno", 0)

    if isinstance(func, ast.Name):
        target = bindings.get(func.id) if func.id not in shadowed else None
        if target is not None:
            for skill, targets in _CALL_RULES.items():
                if target in targets:
                    facts.findings.append(
                        (skill, line, symbol, f"import:{target}", context))
                    break
            if target in _SUBPROCESS_TARGETS and _git_arg_evidence(call):
                facts.findings.append(
                    ("git_operations", line, symbol, f"git-arg:{target}", context))
        # الباني المدمج open() — ما لم يُعد المستخدم تعريفه (محجوب)
        elif func.id == "open" and "open" not in shadowed:
            mode = _open_mode(call)
            if mode is not None:
                if any(ch in mode for ch in "wax"):
                    facts.findings.append(
                        ("file_write", line, symbol, "builtin:open(w)", context))
                else:
                    facts.findings.append(
                        ("file_read", line, symbol, "builtin:open(r)", context))

    elif isinstance(func, ast.Attribute):
        target = _dotted_target(func, bindings, shadowed)
        if target is not None:
            for skill, targets in _CALL_RULES.items():
                if target in targets:
                    facts.findings.append(
                        (skill, line, symbol, f"attr:{target}", context))
                    break
            # أوامر git الصريحة — فحص مستقل (دليلان: تشغيل + إدارة git)
            if target in _SUBPROCESS_TARGETS and _git_arg_evidence(call):
                facts.findings.append(
                    ("git_operations", line, symbol, f"git-arg:{target}", context))
            return
        # pathlib.Path.read_text() — المستقبل معروف (استيراد أو استدعاء بناء)
        if func.attr in _PATHLIB_METHOD_RULES["file_read"] \
                or func.attr in _PATHLIB_METHOD_RULES["file_write"]:
            receiver = _receiver_target(func.value, bindings, shadowed)
            if receiver == _PATHLIB_TARGET:
                for skill, attrs in _PATHLIB_METHOD_RULES.items():
                    if func.attr in attrs:
                        facts.findings.append(
                            (skill, line, symbol,
                             f"attr:{_PATHLIB_TARGET}.{func.attr}", context))
                        break


def _receiver_target(receiver: ast.AST, bindings: Dict[str, str],
                      shadowed: Set[str]) -> Optional[str]:
    """هدف المستقبل إن كان معروفاً: اسم مربوط أو استدعاء بناء لمستورَد."""
    if isinstance(receiver, ast.Name):
        if receiver.id in shadowed:
            return None
        return bindings.get(receiver.id)
    if isinstance(receiver, ast.Call):
        return _receiver_target(receiver.func, bindings, shadowed)
    return None


# ---------------------------------------------------------------------------
# CI — فحص بنيوي لوثائق workflows بعلامات مواقع حقيقية ومطابقة رموز أمر
# ---------------------------------------------------------------------------

def _ci_test_steps(path: str, text: str) -> Tuple[List[Dict[str, Any]], Optional[str],
                                                 List[str]]:
    """خطوات run التي تشغّل أوامر اختبار فعلاً — فحص بنيوي (yaml) بعلامات
    الأسطر الحقيقية ورموز الأوامر (shlex) لا سلاسل جزئية؛ والوثيقة الفاسدة
    خطأ مسمّى لا نجاح صامت، ومفتاح الجذر المعتمد ``jobs`` وحده (بنية steps/run
    تحت أي مفتاح آخر ليست وظيفة CI). الصيغ غير المدعومة (heredoc داخل الخطوة)
    لا يُستنتج منها دليل — تُعلن فجوة مسمّاة. يعيد (الأدلة، خطأ التحليل،
    الصيغ غير المدعومة)."""
    try:
        import yaml
        root = yaml.compose(text)
    except Exception as exc:  # noqa: BLE001 — فاسدة: فجوة مسمّاة لا فشل صامت
        return [], f"{type(exc).__name__}: {exc}".strip(": "), []

    def items(node: Any) -> List[Tuple[Any, Any]]:
        """أزواج (مفتاح، قيمة) لعقدة خرائط yaml — وإلا لا شيء."""
        if getattr(node, "id", "") == "mapping" and isinstance(node.value, list):
            return [(k.value, v) for k, v in node.value]
        return []

    evidence: List[Dict[str, Any]] = []
    unsupported: List[str] = []
    for root_key, jobs_node in items(root):
        if root_key != "jobs":
            continue
        for job_name, job_body in items(jobs_node):
            steps_node = None
            for k, v in items(job_body):
                if k == "steps":
                    steps_node = v
                    break
            if steps_node is None:
                continue
            steps = getattr(steps_node, "value", None) or []
            for step_no, step in enumerate(steps):
                run_node = None
                for k, v in items(step):
                    if k == "run":
                        run_node = v
                        break
                if run_node is None:
                    continue
                run_text = getattr(run_node, "value", None)
                if not isinstance(run_text, str):
                    continue
                if "<<" in run_text:
                    # heredoc: سطر داخل محتوى مكتوب لملف قد يبدو أمراً —
                    # لا يُستنتج منه دليل؛ صيغة غير مدعومة معلنة
                    unsupported.append(
                        f"{path}: jobs.{job_name}.steps[{step_no}].run (heredoc)")
                    continue
                cmd = _match_test_command(run_text)
                if cmd:
                    evidence.append({
                        "skill": "run_tests", "file": path,
                        "line": run_node.start_mark.line + 1,
                        "symbol": f"jobs.{job_name}.steps[{step_no}].run",
                        "rule": f"ci-run:{cmd}", "context": "production"})
    return evidence, None, unsupported


def _match_test_command(run_text: str) -> Optional[str]:
    """أمر اختبار فعلي في نص خطوة run: أول رموز كل سطر أمر (shlex) تطابق
    بادئة أمر معروفة — ``pip install pytest`` و``echo pytest`` ذِكر لا تشغيل."""
    for raw_line in run_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = tuple(shlex.split(line))
        except ValueError:
            continue
        if not tokens:
            continue
        for cmd, prefixes in _CI_TEST_COMMANDS.items():
            for prefix in prefixes:
                if tokens[:len(prefix)] == prefix:
                    return cmd
    return None


# ---------------------------------------------------------------------------
# البناء — إسقاط صرف فوق الحقائق المشتركة (لا مسح جديد)
# ---------------------------------------------------------------------------

def build_capability_genome(shared: Any, *,
                            generated_at: datetime,
                            snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """بناء الجينوم من حقائق ``SharedAnalysis`` — حتمي (الوقت من المستدعي
    إلزامياً). لا يفتح مساراً ولا يعيد مسحاً: المحتوى المقروء من الحقائق،
    والمصرّح به من تقرير المكدس، والنقص يُعلن بتفاصيله لا بعدّاده فقط.
    """
    files = [f for f in shared.files if not f.is_dir]
    py_files = [f for f in files if f.extension in _CODE_EXTENSIONS]

    findings: List[Tuple[str, str, int, str, str, str]] = []
    # (skill, file, line, symbol, rule, context)
    parse_errors: List[str] = []
    unread_py: Dict[str, str] = {}

    for entry in sorted(py_files, key=lambda f: f.path):
        text = shared.contents.get(entry.path)
        if text is None:
            reason = shared.unread.get(entry.path, "not_read")
            unread_py[entry.path] = reason
            continue
        facts = _analyze_python(entry.path, text)
        if facts.parse_error:
            parse_errors.append(f"{entry.path}: {facts.parse_error}")
        for skill, line, symbol, rule, context in facts.findings:
            findings.append((skill, entry.path, line, symbol, rule, context))

    # أوامر CI: فحص بنيوي لوثائق workflows — الفاسدة فجوة مسماة، والصيغ
    # غير المدعومة (heredoc) معلنة لا مُستنتج منها دليل
    ci_parse_errors: List[str] = []
    ci_unsupported: List[str] = []
    for entry in sorted(files, key=lambda f: f.path):
        if not entry.path.replace("\\", "/").startswith(".github/workflows/"):
            continue
        if entry.extension not in (".yml", ".yaml"):
            continue
        text = shared.contents.get(entry.path)
        if text is None:
            continue
        steps, error, unsupported = _ci_test_steps(entry.path, text)
        if error:
            ci_parse_errors.append(f"{entry.path}: {error}")
        ci_unsupported.extend(unsupported)
        findings.extend(
            (s["skill"], s["file"], s["line"], s["symbol"], s["rule"],
             s["context"]) for s in steps)

    # المصرّح به من ملفات الاعتماديات — كل النطاقات (dev أيضاً: pytest)؛
    # تعذر المصدر فجوة مسماة لا قائمة فارغة صامتة
    declared: Dict[str, Set[str]] = {}
    dependency_records: List[Dict[str, Any]] = []
    dependency_records_error: Optional[str] = None
    stack = getattr(shared, "stack", None)
    if stack is not None:
        try:
            from stack_detection import dependency_records as _dr
            dependency_records = _dr(stack)
        except Exception as exc:  # noqa: BLE001 — فجوة مسمّاة لا نجاح صامت
            dependency_records_error = f"{type(exc).__name__}: {exc}"
    for rec in dependency_records:
        name = str(rec.get("name", "")).strip().lower()
        skill = _DECLARED_DEP_SKILLS.get(name)
        if skill:
            declared.setdefault(skill, set()).add(
                f"{rec.get('name')}@{rec.get('ecosystem')}")

    # تجميع المهارات
    skills: Dict[str, Dict[str, Any]] = {}
    all_skill_ids = sorted(set(_CALL_RULES) | set(_PATHLIB_METHOD_RULES)
                            | set(declared) | set(_SKILL_CATEGORIES))
    for skill_id in all_skill_ids:
        skill_findings = sorted(
            (f for f in findings if f[0] == skill_id),
            key=lambda f: (f[1], f[2], f[3], f[4]))
        entries = [
            {"file": f[1], "line": f[2], "symbol": f[3],
             "rule": f[4], "context": f[5]}
            for f in skill_findings]
        production = [e for e in entries if e["context"] == "production"]
        test_only = [e for e in entries if e["context"] == "test"]
        dep_sources = sorted(declared.get(skill_id, set()))
        if production:
            status = "statically_supported"
        elif test_only:
            status = "test_only"
        elif dep_sources:
            status = "declared"
        else:
            status = "not_detected"
        skills[skill_id] = {
            "category": _SKILL_CATEGORIES.get(skill_id, "general"),
            "status": status,
            "findings": entries,
            "declared_in": dep_sources,
        }

    # القدرات: verified بتركيب موثق في رمز واحد مؤهل؛ والتركيب من أدلة
    # الإنتاج وحدها — دليل الاختبار لا يثبت قدرة إنتاج
    capabilities: Dict[str, Dict[str, Any]] = {}
    production_findings = [f for f in findings if f[5] == "production"]
    for cap_id, required in sorted(_CAPABILITY_REQUIREMENTS.items()):
        by_symbol: Dict[Tuple[str, str], Set[str]] = {}
        for f in production_findings:
            if f[0] in required:
                key = (f[1], f[3])
                by_symbol.setdefault(key, set()).add(f[0])
        composed_in = [
            {"file": file, "symbol": symbol}
            for (file, symbol), got in sorted(by_symbol.items())
            if set(required) <= got]
        all_supported = all(
            skills.get(s, {}).get("status") in
            ("statically_supported", "test_only") for s in required)
        all_declared = all(
            skills.get(s, {}).get("status") == "declared"
            or skills.get(s, {}).get("status") in
            ("statically_supported", "test_only") for s in required)
        if composed_in:
            status = "verified"
        elif all_supported:
            status = "candidate"
        elif all_declared:
            status = "declared"
        else:
            status = "absent"
        missing = [s for s in required
                   if skills.get(s, {}).get("status") == "not_detected"]
        capabilities[cap_id] = {
            "required_skills": list(required),
            "status": status,
            "composed_in": composed_in,
            "missing_skills": missing,
        }

    # الفجوات المسمّاة — النقص يُعلن بتفاصيله لا بعدّاده فقط
    gaps: List[str] = []
    if unread_py:
        gaps.append(
            f"python-files-unread: {len(unread_py)} "
            f"({'; '.join(f'{p}: {r}' for p, r in sorted(unread_py.items()))})")
    non_py = sorted({
        str(lang) for lang in (
            getattr(stat, "language", "")
            for stat in (shared.code_languages or {}).values())
        if str(lang).lower() not in _PYTHON_LANGUAGE_KEYS and str(lang)})
    if non_py:
        gaps.append(
            "no-static-extractor-for-languages: " + ", ".join(non_py)
            + " (المستخرج يفهم بيثون ووثائق CI فقط)")
    if parse_errors:
        gaps.append(f"python-parse-errors: {len(parse_errors)} "
                    f"({'; '.join(parse_errors)})")
    if ci_parse_errors:
        gaps.append(f"ci-workflow-parse-errors: {len(ci_parse_errors)} "
                    f"({'; '.join(ci_parse_errors)})")
    if ci_unsupported:
        gaps.append(f"ci-run-unsupported-forms: {len(ci_unsupported)} "
                    f"({'; '.join(ci_unsupported)}) — لا يُستنتج منها دليل")
    for path, reason in sorted(shared.scan_errors.items()):
        gaps.append(f"scan-error: {path}: {reason}")
    if dependency_records_error:
        gaps.append(f"dependency-records-unavailable: {dependency_records_error}")
    gaps.append(
        "performance-metrics-unmeasured: accuracy/cost/duration/success-rate "
        "غير مقيسة — لا تُدّعى")
    gaps.append(
        "absence-of-evidence: not_detected ليس إثبات غياب — النطاق بيثون "
        "AST ووثائق CI فقط")

    # التغطية — مقيسة من الحقائق فقط
    read_py = [f for f in py_files if f.path in shared.contents]
    coverage = {
        "python_files": len(py_files),
        "python_files_analyzed": len(read_py) - len(parse_errors),
        "python_files_unread": len(unread_py),
        "files_total": len(files),
        "files_read": sum(1 for f in files if f.path in shared.contents),
        "files_unread": sum(1 for f in files if f.path not in shared.contents),
    }

    repo = {
        "name": shared.meta.get("name", ""),
        "url": shared.meta.get("url", "") or shared.source_url,
        "owner": shared.meta.get("owner", ""),
        "branch": shared.source_branch,
        "commit": shared.source_commit,
        "path": shared.source_path,
    }
    if not repo["commit"]:
        gaps.append("commit-unknown: تحليل مسار محلي بلا افتراضات git (ADR-0005)")

    # العدادات مفصولة: الكتالوج من نتائج هذا المستودع — لا يُحسب ما لم يُرصد
    supported = sum(1 for s in skills.values()
                    if s["status"] in ("statically_supported", "test_only"))
    declared_skills = sum(1 for s in skills.values() if s["status"] == "declared")
    verified_caps = sum(1 for c in capabilities.values() if c["status"] == "verified")
    candidate_caps = sum(1 for c in capabilities.values()
                         if c["status"] == "candidate")

    return {
        "capability": "CapabilityGenome",
        "genome_schema_version": GENOME_SCHEMA_VERSION,
        "rules_version": RULES_VERSION,
        "generated_at": generated_at.isoformat(),
        "analysis_snapshot": snapshot or {"identity": "unrecorded"},
        "repository": repo,
        "catalog_skill_count": len(_SKILL_CATEGORIES) or len(skills),
        "catalog_capability_count": len(_CAPABILITY_REQUIREMENTS),
        "supported_skill_count": supported,
        "declared_skill_count": declared_skills,
        "verified_capability_count": verified_caps,
        "candidate_capability_count": candidate_caps,
        "skills": skills,
        "capabilities": capabilities,
        "coverage": coverage,
        "unread_python_files": unread_py,
        "python_parse_errors": parse_errors,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# القدرة — مدخل واحد فوق الخط الموحد (ADR-0005)، حل بالاسم عبر التسجيل
# ---------------------------------------------------------------------------

class CapabilityGenomeCapability(ICapability):
    """R-W2-012 — تقرير جينوم القدرات لمستودع (URL أو مسار محلي).

    فوق الخط الموحد مباشرة (لا استنساخ/مسح خاص): ``analyze_url`` عبر المزوّد أو
    ``analyze_path`` محلياً، ثم الإسقاط الحتمي ``build_capability_genome``.
    """

    name = "CapabilityGenome"
    description = ("Builds the capability genome report (skills + composed "
                   "capabilities with named evidence and gaps) from the "
                   "unified repository analysis line")
    skills = ["CloneRepository", "ReadRepository"]
    version = "1.0.0"

    def execute(self, input_data: Any) -> Dict[str, Any]:
        if not isinstance(input_data, dict):
            raise ValueError("input must be a dict with url or repo_path")
        url = input_data.get("url")
        repo_path = input_data.get("repo_path") or input_data.get("path")
        if url and repo_path:
            raise ValueError("give either url or repo_path, not both")
        from capabilities.analysis_service import get_analysis_service
        service = get_analysis_service()
        if url:
            shared = service.analyze_url(
                url, input_data.get("branch", "main"))
        elif repo_path:
            shared = service.analyze_path(
                repo_path, policy=input_data.get("scan_policy"))
        else:
            raise ValueError("input needs one of: url, repo_path")
        return build_capability_genome(
            shared, generated_at=datetime.now(timezone.utc))

    def __init__(self):
        """القيم معلنة كسمات صف (نمط R-W2-007)؛ الباني محفوظ للتوافق (G2)."""
