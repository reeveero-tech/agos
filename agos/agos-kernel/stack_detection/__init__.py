"""كشف الأطر من ملفات الاعتماديات — المصدر الموحَّد لقرار «ما الأطر في هذا المستودع؟» (R-W2-001).

القاعدة الحاكمة لهذه الوحدة:
    الإطار لا يُعلَن إلا إذا ورد **اعتماديةً تشغيلية** (runtime/peer) في ملف اعتماديات
    حقيقي (requirements*.txt, pyproject.toml, setup.cfg, setup.py, Pipfile, package.json,
    Gemfile, composer.json, pom.xml, build.gradle[.kts], go.mod, Cargo.toml, pubspec.yaml).
    ذِكر اسم الإطار في README أو في التوثيق أو في نص الشيفرة أو في اسم ملف (app.py,
    manage.py, settings.py …) **ليس دليلاً**.

كل قرار مصحوب بدليل: (الإطار، الاعتمادية، الملف، النظام البيئي، النطاق، هل احتُسب).
الاعتماديات ذات النطاق dev/test/optional/build/example تُسجَّل في الأدلة لكنها لا تُحتسب.

الوحدة نقية (مكتبة Python القياسية فقط) ولا تقرأ القرص إلا عبر ``read_manifests``.
"""
from __future__ import annotations

import ast
import configparser
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

try:  # Python ≥ 3.11
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - المشروع يتطلب 3.11+
    _toml = None  # type: ignore[assignment]

__all__ = [
    "COUNTED_SCOPES",
    "Dependency",
    "Evidence",
    "StackReport",
    "detect_stack",
    "detect_frameworks",
    "framework_for",
    "is_manifest",
    "iter_counted",
    "manifest_kind",
    "parse_manifest",
    "read_manifests",
    "normalize_name",
]

# النطاقات التي تجعل الاعتمادية دليلاً على إطار المشروع نفسه.
COUNTED_SCOPES = frozenset({"runtime", "peer"})

# مجلدات لا تمثل المشروع: اعتماديات مُورَّدة أو بيئات افتراضية — تُتجاهل كلياً.
SKIP_DIRS = frozenset({
    ".git", "node_modules", "bower_components", "vendor", "venv", ".venv", "env",
    "site-packages", "__pycache__", ".tox", ".nox", "dist", "build", ".mypy_cache",
})

# مجلدات أمثلة/اختبارات/توثيق: تُقرأ ملفاتها لكن نطاقها يصبح "example" فلا تُحتسب.
EXAMPLE_DIRS = frozenset({
    "example", "examples", "sample", "samples", "demo", "demos", "docs", "doc",
    "test", "tests", "testing", "fixtures", "testdata", "__tests__", "benchmarks",
})

# ملفات requirements ذات أسماء تدل على أدوات التطوير.
_DEV_REQ_HINTS = ("dev", "test", "doc", "lint", "ci", "bench", "typing", "type", "style")

# ---------------------------------------------------------------------------
# خرائط الأسماء: اسم الحزمة (بعد التطبيع) → الإطار. المطابقة تامة لا جزئية.
# ---------------------------------------------------------------------------
PYPI_FRAMEWORKS: Dict[str, str] = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "tensorflow-cpu": "TensorFlow",
    "tensorflow-gpu": "TensorFlow",
    "langchain": "LangChain",
    "langchain-core": "LangChain",
    "langchain-community": "LangChain",
    "llama-index": "LlamaIndex",
    "llama-index-core": "LlamaIndex",
}
NPM_FRAMEWORKS: Dict[str, str] = {
    "react": "React",
    "react-dom": "React",
    "vue": "Vue",
    "@angular/core": "Angular",
    "next": "Next.js",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "fastify": "Fastify",
}
GEM_FRAMEWORKS: Dict[str, str] = {"rails": "Rails", "railties": "Rails"}
COMPOSER_FRAMEWORKS: Dict[str, str] = {"laravel/framework": "Laravel"}
GO_FRAMEWORKS: Dict[str, str] = {
    "github.com/gin-gonic/gin": "Gin",
    "github.com/labstack/echo": "Echo",
    "github.com/gofiber/fiber": "Fiber",
}
CARGO_FRAMEWORKS: Dict[str, str] = {"axum": "Axum", "actix-web": "Actix Web", "rocket": "Rocket"}
PUB_FRAMEWORKS: Dict[str, str] = {"flutter": "Flutter"}
# Maven/Gradle: المطابقة على groupId (أو معرّف الإضافة) بالبادئة org.springframework.
_SPRING_PREFIX = "org.springframework"


@dataclass(frozen=True)
class Dependency:
    """اعتمادية واحدة كما وردت في ملف اعتماديات."""

    name: str          # الاسم المطبَّع (pypi: أحرف صغيرة و'-'؛ maven: group:artifact)
    ecosystem: str     # pypi | npm | rubygems | composer | maven | go | cargo | pub
    scope: str         # runtime | peer | dev | optional | build | indirect | example
    manifest: str      # المسار النسبي لملف الاعتماديات


@dataclass(frozen=True)
class Evidence:
    """دليل قرار إطار: لماذا (أو لماذا لا) يُعَدّ الإطار جزءاً من المشروع."""

    framework: str
    dependency: str
    manifest: str
    ecosystem: str
    scope: str
    counted: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class StackReport:
    """نتيجة الكشف: الأطر المحتسبة، الأدلة، بيئات التشغيل، الملفات المقروءة، وأخطاء التحليل."""

    frameworks: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    runtimes: List[str] = field(default_factory=list)
    manifests: List[str] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "frameworks": list(self.frameworks),
            "evidence": [e.to_dict() for e in self.evidence],
            "runtimes": list(self.runtimes),
            "manifests": list(self.manifests),
            "dependencies": [asdict(d) for d in self.dependencies],
            "errors": dict(self.errors),
        }


# ---------------------------------------------------------------------------
# أدوات عامة
# ---------------------------------------------------------------------------
_PEP503 = re.compile(r"[-_.]+")
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize_name(name: str, ecosystem: str = "pypi") -> str:
    """تطبيع اسم الحزمة: PEP 503 لـ pypi، وأحرف صغيرة لبقية الأنظمة."""
    name = name.strip()
    if ecosystem == "pypi":
        return _PEP503.sub("-", name).lower()
    return name.lower()


def _posix(path: str) -> PurePosixPath:
    return PurePosixPath(str(path).replace("\\", "/").lstrip("./") or ".")


def manifest_kind(path: str) -> Optional[str]:
    """نوع ملف الاعتماديات حسب اسمه، أو None إن لم يكن ملف اعتماديات."""
    p = _posix(path)
    name = p.name
    low = name.lower()
    if low.endswith(".txt") and (low.startswith("requirements") or p.parent.name.lower() == "requirements"):
        return "requirements"
    return {
        "pyproject.toml": "pyproject",
        "setup.cfg": "setup.cfg",
        "setup.py": "setup.py",
        "Pipfile": "pipfile",
        "package.json": "package.json",
        "Gemfile": "gemfile",
        "composer.json": "composer",
        "pom.xml": "pom",
        "build.gradle": "gradle",
        "build.gradle.kts": "gradle",
        "go.mod": "go.mod",
        "Cargo.toml": "cargo",
        "pubspec.yaml": "pubspec",
    }.get(name)


def is_manifest(path: str) -> bool:
    """هل المسار ملف اعتماديات يُعتدّ به (وليس داخل مجلد مُورَّد)؟"""
    if manifest_kind(path) is None:
        return False
    return not any(part in SKIP_DIRS for part in _posix(path).parts[:-1])


def _is_example_path(path: str) -> bool:
    return any(part.lower() in EXAMPLE_DIRS for part in _posix(path).parts[:-1])


def _req_file_scope(path: str) -> str:
    p = _posix(path)
    stem = p.name.lower()[: -len(".txt")]
    if stem.startswith("requirements"):
        stem = stem[len("requirements"):]
    tokens = [t for t in re.split(r"[-_.]+", stem) if t]
    if any(t.startswith(h) for t in tokens for h in _DEV_REQ_HINTS):
        return "dev"
    if p.parent.name.lower() == "requirements" and any(stem.startswith(h) for h in _DEV_REQ_HINTS):
        return "dev"
    return "runtime"


# ---------------------------------------------------------------------------
# محللات ملفات الاعتماديات — كل محلل يعيد [(name, ecosystem, scope)]
# ---------------------------------------------------------------------------
Parsed = List[Tuple[str, str, str]]


def _pep508_name(spec: str) -> Optional[str]:
    spec = spec.split(";", 1)[0].strip()
    if not spec or spec.startswith(("-", "#", "git+", "http:", "https:", "file:")):
        return None
    m = _REQ_NAME.match(spec)
    return m.group(1) if m else None


def _parse_requirements(text: str, path: str) -> Parsed:
    scope = _req_file_scope(path)
    out: Parsed = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-e ", "--editable")):
            m = re.search(r"#egg=([A-Za-z0-9._-]+)", raw)
            if m:
                out.append((m.group(1), "pypi", scope))
            continue
        if line.startswith("-"):  # -r, -c, --index-url ...
            continue
        if " @ " in line:
            line = line.split(" @ ", 1)[0]
        name = _pep508_name(line)
        if name:
            out.append((name, "pypi", scope))
    return out


def _pep508_list(items: object, scope: str) -> Parsed:
    out: Parsed = []
    if isinstance(items, (list, tuple)):
        for item in items:
            if isinstance(item, str):
                name = _pep508_name(item)
                if name:
                    out.append((name, "pypi", scope))
    return out


def _poetry_table(table: object, scope: str) -> Parsed:
    out: Parsed = []
    if isinstance(table, dict):
        for name in table:
            if str(name).lower() != "python":
                out.append((str(name), "pypi", scope))
    return out


def _parse_pyproject(text: str, path: str) -> Parsed:
    if _toml is None:  # pragma: no cover
        raise RuntimeError("tomllib غير متاح")
    data = _toml.loads(text)
    out: Parsed = []
    project = data.get("project", {}) or {}
    out += _pep508_list(project.get("dependencies"), "runtime")
    for extra in (project.get("optional-dependencies") or {}).values():
        out += _pep508_list(extra, "optional")
    for group in (data.get("dependency-groups") or {}).values():
        out += _pep508_list(group, "dev")
    out += _pep508_list((data.get("build-system") or {}).get("requires"), "build")
    poetry = (data.get("tool") or {}).get("poetry") or {}
    out += _poetry_table(poetry.get("dependencies"), "runtime")
    out += _poetry_table(poetry.get("dev-dependencies"), "dev")
    for gname, group in (poetry.get("group") or {}).items():
        deps = (group or {}).get("dependencies")
        out += _poetry_table(deps, "runtime" if gname == "main" else "dev")
    pdm = (data.get("tool") or {}).get("pdm") or {}
    for group in (pdm.get("dev-dependencies") or {}).values():
        out += _pep508_list(group, "dev")
    return out


def _parse_setup_cfg(text: str, path: str) -> Parsed:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_string(text)
    out: Parsed = []
    if cfg.has_option("options", "install_requires"):
        out += _pep508_list(cfg.get("options", "install_requires").splitlines(), "runtime")
    if cfg.has_option("options", "tests_require"):
        out += _pep508_list(cfg.get("options", "tests_require").splitlines(), "dev")
    if cfg.has_section("options.extras_require"):
        for _key, value in cfg.items("options.extras_require"):
            out += _pep508_list(value.splitlines(), "optional")
    return out


def _literal(node: ast.AST, names: Mapping[str, ast.AST]) -> object:
    if isinstance(node, ast.Name) and node.id in names:
        node = names[node.id]
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _parse_setup_py(text: str, path: str) -> Parsed:
    """يحلل setup.py بشجرة AST دون تنفيذه: قيم حرفية أو متغيرات مُسندة بقيم حرفية."""
    tree = ast.parse(text)
    names: Dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            names[node.targets[0].id] = node.value
    out: Parsed = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fname = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
        if fname != "setup":
            continue
        for kw in node.keywords:
            value = _literal(kw.value, names) if kw.arg else None
            if kw.arg == "install_requires":
                out += _pep508_list(value, "runtime")
            elif kw.arg == "tests_require":
                out += _pep508_list(value, "dev")
            elif kw.arg == "extras_require" and isinstance(value, dict):
                for extra in value.values():
                    out += _pep508_list(extra, "optional")
    return out


def _parse_pipfile(text: str, path: str) -> Parsed:
    if _toml is None:  # pragma: no cover
        raise RuntimeError("tomllib غير متاح")
    data = _toml.loads(text)
    return _poetry_table(data.get("packages"), "runtime") + _poetry_table(data.get("dev-packages"), "dev")


def _parse_package_json(text: str, path: str) -> Parsed:
    data = json.loads(text)
    out: Parsed = []
    if not isinstance(data, dict):
        return out
    for key, scope in (("dependencies", "runtime"), ("peerDependencies", "peer"),
                       ("devDependencies", "dev"), ("optionalDependencies", "optional")):
        table = data.get(key)
        if isinstance(table, dict):
            out += [(str(n), "npm", scope) for n in table]
    return out


_GEM = re.compile(r"""^\s*gem\s*\(?\s*['"]([^'"]+)['"]""")
_GROUP_OPEN = re.compile(r"^\s*group\b(.*)\bdo\b")
_BLOCK_OPEN = re.compile(r"\bdo\b(\s*\|[^|]*\|)?\s*$")
_GEM_GROUP_KW = re.compile(r"""(?:group|groups)\s*(?::|=>)\s*\[?([^\]\n]*)""")


def _parse_gemfile(text: str, path: str) -> Parsed:
    out: Parsed = []
    stack: List[bool] = []  # لكل كتلة مفتوحة: هل هي مجموعة تطوير/اختبار؟
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        g = _GROUP_OPEN.match(line)
        if g:
            stack.append(bool(re.search(r"development|test", g.group(1))))
            continue
        if re.match(r"^\s*end\b", line):
            if stack:
                stack.pop()
            continue
        m = _GEM.match(line)
        if m:
            dev = any(stack)
            kw = _GEM_GROUP_KW.search(line)
            if kw and re.search(r"development|test", kw.group(1)):
                dev = True
            out.append((m.group(1), "rubygems", "dev" if dev else "runtime"))
            continue
        if _BLOCK_OPEN.search(line):  # كتل أخرى (platforms/source ... do)
            stack.append(False)
    return out


def _parse_composer(text: str, path: str) -> Parsed:
    data = json.loads(text)
    out: Parsed = []
    if not isinstance(data, dict):
        return out
    for key, scope in (("require", "runtime"), ("require-dev", "dev")):
        table = data.get(key)
        if isinstance(table, dict):
            for n in table:
                n = str(n)
                if n == "php" or n.startswith("ext-") or "/" not in n:
                    continue
                out.append((n, "composer", scope))
    return out


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_pom(text: str, path: str) -> Parsed:
    root = ET.fromstring(text)
    out: Parsed = []

    def child(el: ET.Element, name: str) -> str:
        for c in el:
            if _strip_ns(c.tag) == name:
                return (c.text or "").strip()
        return ""

    for el in root:
        tag = _strip_ns(el.tag)
        if tag == "parent":
            g, a = child(el, "groupId"), child(el, "artifactId")
            if g:
                out.append((f"{g}:{a}", "maven", "runtime"))
        elif tag == "dependencies":
            for dep in el:
                if _strip_ns(dep.tag) != "dependency":
                    continue
                g, a = child(dep, "groupId"), child(dep, "artifactId")
                scope = child(dep, "scope").lower()
                optional = child(dep, "optional").lower() == "true"
                s = "dev" if scope == "test" else "optional" if optional else \
                    "build" if scope == "provided" else "runtime"
                if g:
                    out.append((f"{g}:{a}", "maven", s))
    # dependencyManagement وbuild/plugins لا تُعدّ اعتماديات تشغيلية.
    return out


_GRADLE_CONF = re.compile(
    r"""^\s*([A-Za-z]+)\s*\(?\s*(?:platform\s*\(\s*)?['"]([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+)""")
_GRADLE_PLUGIN = re.compile(r"""\bid\s*\(?\s*['"](org\.springframework[A-Za-z0-9_.\-]*)['"]""")
_GRADLE_RUNTIME = {"implementation", "api", "compile", "runtimeOnly", "runtime", "compileOnly"}


def _parse_gradle(text: str, path: str) -> Parsed:
    out: Parsed = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0]
        m = _GRADLE_CONF.match(line)
        if m:
            conf = m.group(1)
            scope = "runtime" if conf in _GRADLE_RUNTIME else \
                "dev" if conf.lower().startswith("test") else "build"
            out.append((f"{m.group(2)}:{m.group(3)}", "maven", scope))
            continue
        p = _GRADLE_PLUGIN.search(line)
        if p:
            out.append((f"{p.group(1)}:plugin", "maven", "runtime"))
    return out


_GO_REQ = re.compile(r"^\s*([A-Za-z0-9._~\-/]+)\s+v[0-9][^\s]*\s*(//\s*indirect)?")


def _parse_go_mod(text: str, path: str) -> Parsed:
    out: Parsed = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line.startswith(")"):
            in_block = False
            continue
        if line.startswith("require "):
            line = line[len("require "):]
        elif not in_block:
            continue
        m = _GO_REQ.match(line)
        if m:
            out.append((m.group(1), "go", "indirect" if m.group(2) else "runtime"))
    return out


def _parse_cargo(text: str, path: str) -> Parsed:
    if _toml is None:  # pragma: no cover
        raise RuntimeError("tomllib غير متاح")
    data = _toml.loads(text)
    out: Parsed = []

    def table(t: object, scope: str) -> None:
        if isinstance(t, dict):
            for name, spec in t.items():
                real = spec.get("package", name) if isinstance(spec, dict) else name
                opt = isinstance(spec, dict) and spec.get("optional") is True
                out.append((str(real), "cargo", "optional" if opt and scope == "runtime" else scope))

    table(data.get("dependencies"), "runtime")
    table(data.get("dev-dependencies"), "dev")
    table(data.get("build-dependencies"), "build")
    for target in (data.get("target") or {}).values():
        if isinstance(target, dict):
            table(target.get("dependencies"), "runtime")
            table(target.get("dev-dependencies"), "dev")
    workspace = data.get("workspace") or {}
    table(workspace.get("dependencies"), "runtime")
    return out


def _parse_pubspec(text: str, path: str) -> Parsed:
    """pubspec.yaml بلا مكتبة YAML: مفاتيح المستوى الثاني داخل dependencies/dev_dependencies."""
    out: Parsed = []
    section: Optional[str] = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            key = line.split(":", 1)[0].strip()
            section = {"dependencies": "runtime", "dev_dependencies": "dev"}.get(key)
            continue
        if section and indent == 2 and ":" in line:
            out.append((line.split(":", 1)[0].strip(), "pub", section))
    return out


_PARSERS = {
    "requirements": _parse_requirements,
    "pyproject": _parse_pyproject,
    "setup.cfg": _parse_setup_cfg,
    "setup.py": _parse_setup_py,
    "pipfile": _parse_pipfile,
    "package.json": _parse_package_json,
    "gemfile": _parse_gemfile,
    "composer": _parse_composer,
    "pom": _parse_pom,
    "gradle": _parse_gradle,
    "go.mod": _parse_go_mod,
    "cargo": _parse_cargo,
    "pubspec": _parse_pubspec,
}

_RUNTIME_OF_KIND = {
    "requirements": "Python", "pyproject": "Python", "setup.cfg": "Python", "setup.py": "Python",
    "pipfile": "Python", "package.json": "Node.js", "gemfile": "Ruby", "composer": "PHP",
    "pom": "JVM", "gradle": "JVM", "go.mod": "Go", "cargo": "Rust", "pubspec": "Dart",
}


def parse_manifest(path: str, text: str) -> List[Dependency]:
    """يحلل ملف اعتماديات واحداً إلى قائمة Dependency (يرفع استثناء عند ملف مشوَّه)."""
    kind = manifest_kind(path)
    if kind is None:
        return []
    example = _is_example_path(path)
    deps: List[Dependency] = []
    for name, eco, scope in _PARSERS[kind](text, path):
        deps.append(Dependency(
            name=normalize_name(name, eco),
            ecosystem=eco,
            scope="example" if example else scope,
            manifest=str(_posix(path)),
        ))
    return deps


def framework_for(dep: Dependency) -> Optional[str]:
    """الإطار الذي تمثّله اعتمادية (مطابقة تامة للاسم المطبَّع)، أو None."""
    if dep.ecosystem == "pypi":
        return PYPI_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "npm":
        if dep.name == "vue" or dep.name.startswith("@vue/runtime"):
            return "Vue"
        return NPM_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "rubygems":
        return GEM_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "composer":
        return COMPOSER_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "go":
        base = re.sub(r"/v[0-9]+$", "", dep.name)
        return GO_FRAMEWORKS.get(base)
    if dep.ecosystem == "cargo":
        return CARGO_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "pub":
        return PUB_FRAMEWORKS.get(dep.name)
    if dep.ecosystem == "maven":
        group = dep.name.split(":", 1)[0]
        if group == _SPRING_PREFIX or group.startswith(_SPRING_PREFIX + "."):
            return "Spring"
    return None


def detect_stack(files: Mapping[str, Optional[str]]) -> StackReport:
    """يكشف الأطر من خريطة {مسار نسبي: محتوى}. الملفات غير الاعتمادية تُتجاهل تماماً."""
    report = StackReport()
    frameworks: Dict[str, None] = {}
    runtimes: Dict[str, None] = {}
    for path in sorted(files):
        if not is_manifest(path):
            continue
        text = files[path]
        rel = str(_posix(path))
        if text is None:
            report.errors[rel] = "المحتوى غير متاح"
            continue
        try:
            deps = parse_manifest(rel, text)
        except Exception as exc:  # ملف مشوَّه: يُسجَّل ولا يُخترع منه شيء
            report.errors[rel] = f"{type(exc).__name__}: {exc}"
            continue
        report.manifests.append(rel)
        if not _is_example_path(rel):
            runtimes.setdefault(_RUNTIME_OF_KIND[manifest_kind(rel) or ""], None)
        for dep in deps:
            report.dependencies.append(dep)
            fw = framework_for(dep)
            if fw is None:
                continue
            counted = dep.scope in COUNTED_SCOPES
            report.evidence.append(Evidence(fw, dep.name, dep.manifest, dep.ecosystem, dep.scope, counted))
            if counted:
                frameworks.setdefault(fw, None)
    report.frameworks = sorted(frameworks)
    report.runtimes = sorted(runtimes)
    return report


def detect_frameworks(files: Mapping[str, Optional[str]]) -> List[str]:
    """واجهة مختصرة: قائمة الأطر المحتسبة مرتبة."""
    return detect_stack(files).frameworks


def read_manifests(root: "os.PathLike[str] | str", max_bytes: int = 1_000_000) -> Dict[str, str]:
    """يقرأ ملفات الاعتماديات فقط من مجلد على القرص (يتخطى المجلدات المُورَّدة)."""
    base = Path(root)
    out: Dict[str, str] = {}
    if not base.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            rel = full.relative_to(base).as_posix()
            if not is_manifest(rel) or full.is_symlink():
                continue
            try:
                if full.stat().st_size > max_bytes:
                    continue
                out[rel] = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


def iter_counted(report: StackReport) -> Iterable[Evidence]:
    """الأدلة المحتسبة فقط."""
    return (e for e in report.evidence if e.counted)
