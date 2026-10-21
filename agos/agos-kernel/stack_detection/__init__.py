"""كشف الأطر من ملفات الاعتماديات — المصدر الموحَّد لقرار «ما الأطر في هذا المستودع؟» (R-W2-001).

القاعدة الحاكمة لهذه الوحدة:
    الإطار لا يُعلَن إلا إذا ورد **اعتماديةً تشغيلية** (runtime/peer) في ملف اعتماديات
    حقيقي (requirements*.txt, pyproject.toml, setup.cfg, setup.py, Pipfile, package.json,
    Gemfile, composer.json, pom.xml, build.gradle[.kts], go.mod, Cargo.toml, pubspec.yaml).
    ذِكر اسم الإطار في README أو في التوثيق أو في نص الشيفرة أو في اسم ملف (app.py,
    manage.py, settings.py …) **ليس دليلاً**.

كل قرار مصحوب بدليل: (الإطار، الاعتمادية، الملف، النظام البيئي، النطاق، هل احتُسب).
الاعتماديات ذات النطاق dev/test/optional/build/indirect/local/example تُسجَّل في الأدلة لكنها لا
تُحتسب. أب Maven وإضافة Gradle (parent/plugin) دليلان على الإطار لا اعتماديتان.

R-W2-002: الوحدة نفسها هي مصدر ``dependencies`` (``project_dependencies``: runtime/peer
المباشرة) و``dependency_details`` (``dependency_records``) ومديري الحزم
(``detect_package_managers``).

R-W2-003: الوحدة أيضاً مصدر وزن اللغات (``language_weights``: أسطر وملفات لكل لغة)
واللغة الرئيسية (``primary_language``: الأكثر أسطراً) وقراءة ملفات الكود من القرص
(``read_code_files``).

الوحدة نقية (مكتبة Python القياسية فقط) ولا تقرأ القرص إلا عبر ``read_manifests``
و``read_code_files``.
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
    "FRAMEWORK_SCOPES",
    "Dependency",
    "Evidence",
    "StackReport",
    "detect_stack",
    "detect_frameworks",
    "detect_package_managers",
    "detect_package_managers_at",
    "dependency_records",
    "project_dependencies",
    "framework_for",
    "is_manifest",
    "iter_counted",
    "manifest_kind",
    "parse_manifest",
    "read_manifests",
    "language_weights",
    "primary_language",
    "language_breakdown",
    "read_code_files",
    "LanguageStat",
    "LANGUAGE_EXTENSIONS",
    "is_relevant_hidden",
    "RELEVANT_HIDDEN_DIRS",
    "RELEVANT_HIDDEN_FILES",
    "detect_entry_points",
    "directory_tree",
    "detect_config_files",
    "CONFIG_SUFFIXES",
    "CONFIG_NAMES",
    "normalize_name",
]

# النطاقات التي تجعل الاعتمادية اعتماديةً مباشرة يحتاجها المشروع ليعمل (R-W2-002).
COUNTED_SCOPES = frozenset({"runtime", "peer"})
# النطاقات التي تُعدّ دليلاً على إطار: ما سبق + أب Maven (spring-boot-starter-parent) وإضافة
# Gradle (org.springframework.boot) — دليلان على الإطار لكنهما ليسا اعتماديتين.
FRAMEWORK_SCOPES = COUNTED_SCOPES | frozenset({"parent", "plugin"})
# أسبقيات مسارات/إشارات محلية: حزم داخل المستودع نفسه (workspace) لا اعتماديات خارجية.
_LOCAL_NPM_PREFIXES = ("file:", "link:", "workspace:", "portal:")

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
    scope: str         # runtime | peer | dev | optional | build | indirect | local | parent | plugin | example
    manifest: str      # المسار النسبي لملف الاعتماديات
    specifier: str = ""  # قيد الإصدار كما كُتب (">=2.0" / "^18.2.0" / "v1.9.1" / "${spring.version}") — R-W2-002


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
    if low.endswith(".gemspec") and len(low) > len(".gemspec"):
        return "gemspec"
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
    if any(t.startswith("build") for t in tokens):
        return "build"
    if any(t.startswith(h) for t in tokens for h in _DEV_REQ_HINTS):
        return "dev"
    if p.parent.name.lower() == "requirements" and stem.startswith("build"):
        return "build"
    if p.parent.name.lower() == "requirements" and any(stem.startswith(h) for h in _DEV_REQ_HINTS):
        return "dev"
    return "runtime"


# ---------------------------------------------------------------------------
# محللات ملفات الاعتماديات — كل محلل يعيد [(name, ecosystem, scope)]
# ---------------------------------------------------------------------------
# (name, ecosystem, scope[, specifier]) — المحللات القديمة تعيد ثلاثية والجديدة رباعية.
Parsed = List[Tuple[str, ...]]


def _pep508_specifier(spec: str, name: str) -> str:
    """ما بعد الاسم في متطلب PEP 508: بلا extras وبلا markers (``flask[async]>=2 ; x`` → ``>=2``)."""
    rest = spec.split(";", 1)[0].strip()[len(name):].strip()
    if rest.startswith("["):
        rest = rest.split("]", 1)[-1].strip()
    if rest.startswith("@"):
        return rest  # مرجع مباشر: "@ https://..."
    return rest.lstrip("(").rstrip(")").replace(" ", "")


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
            name = _pep508_name(line.split(" @ ", 1)[0])
            if name:
                out.append((name, "pypi", scope, "@ " + line.split(" @ ", 1)[1].strip()))
            continue
        name = _pep508_name(line)
        if name:
            out.append((name, "pypi", scope, _pep508_specifier(line, name)))
    return out


def _pep508_list(items: object, scope: str) -> Parsed:
    out: Parsed = []
    if isinstance(items, (list, tuple)):
        for item in items:
            if isinstance(item, str):
                name = _pep508_name(item)
                if name:
                    out.append((name, "pypi", scope, _pep508_specifier(item, name)))
    return out


def _spec_value(spec: object) -> str:
    """قيد الإصدار من قيمة جدول (نص، أو {version=...}، أو {git/path=...})."""
    if isinstance(spec, str):
        return spec.strip()
    if isinstance(spec, dict):
        for key in ("version", "git", "path", "url"):
            if isinstance(spec.get(key), str):
                return spec[key] if key == "version" else f"{key}:{spec[key]}"
    return ""


def _poetry_table(table: object, scope: str) -> Parsed:
    out: Parsed = []
    if isinstance(table, dict):
        for name, spec in table.items():
            if str(name).lower() != "python":
                local = isinstance(spec, dict) and "path" in spec
                out.append((str(name), "pypi", "local" if local else scope, _spec_value(spec)))
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
            for n, v in table.items():
                spec = _spec_value(v)
                local = scope in ("runtime", "peer") and spec.startswith(_LOCAL_NPM_PREFIXES)
                out.append((str(n), "npm", "local" if local else scope, spec))
    return out


_GEM = re.compile(r"""^\s*gem\s*\(?\s*['"]([^'"]+)['"]""")
_QUOTED = re.compile(r"""['"]([^'"]*)['"]""")


def _gem_versions(line: str, after: int) -> str:
    """القيود النصية بعد اسم الجوهرة حتى أول خيار مسمّى (``'~> 7.0', '>= 7.0.1'``)."""
    rest = line[after:]
    rest = re.split(r",\s*[A-Za-z_]+\s*(?::|=>)", rest, maxsplit=1)[0]
    return ", ".join(q for q in _QUOTED.findall(rest) if re.match(r"^\s*[~<>=!]*\s*[0-9]", q))
_GROUP_OPEN = re.compile(r"^\s*group\b(.*)\bdo\b")
_BLOCK_OPEN = re.compile(r"\bdo\b(\s*\|[^|]*\|)?\s*$")
_GEM_GROUP_KW = re.compile(r"""(?:group|groups)\s*(?::|=>)\s*\[?([^\]\n]*)""")


def _parse_gemfile(text: str, path: str) -> Parsed:
    out: Parsed = []
    # Gemfile فيه ``gemspec``: مستودع مكتبة؛ اعتمادياتها التشغيلية في ‎*.gemspec وGemfile بيئة
    # تطويرها (اصطلاح Bundler) — فكل جواهره هنا نطاقها dev.
    library = re.search(r"^\s*gemspec\b", text, re.M) is not None
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
            local = re.search(r"(?:\bpath\s*:|:path\s*=>)", line) is not None
            scope = "local" if local else "dev" if (dev or library) else "runtime"
            out.append((m.group(1), "rubygems", scope, _gem_versions(line, m.end())))
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
            for n, v in table.items():
                n = str(n)
                if n == "php" or n.startswith("ext-") or "/" not in n:
                    continue
                out.append((n, "composer", scope, _spec_value(v)))
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
                out.append((f"{g}:{a}", "maven", "parent", child(el, "version")))
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
                    out.append((f"{g}:{a}", "maven", s, child(dep, "version")))
    # dependencyManagement وbuild/plugins لا تُعدّ اعتماديات تشغيلية.
    return out


_GRADLE_CONF = re.compile(
    r"""^\s*([A-Za-z]+)\s*\(?\s*(?:platform\s*\(\s*)?['"]([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+)(?::([^'"@:]+))?""")
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
            out.append((f"{m.group(2)}:{m.group(3)}", "maven", scope, m.group(4) or ""))
            continue
        p = _GRADLE_PLUGIN.search(line)
        if p:
            out.append((f"{p.group(1)}:plugin", "maven", "plugin"))
    return out


_GO_REQ = re.compile(r"^\s*([A-Za-z0-9._~\-/]+)\s+(v[0-9][^\s]*)\s*(//\s*indirect)?")


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
            out.append((m.group(1), "go", "indirect" if m.group(3) else "runtime", m.group(2)))
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
                local = isinstance(spec, dict) and "path" in spec
                eff = "local" if local else "optional" if opt and scope == "runtime" else scope
                out.append((str(real), "cargo", eff, _spec_value(spec)))

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
            key, _, value = line.partition(":")
            out.append((key.strip(), "pub", section, value.strip().strip("'\"")))
    return out


_GEMSPEC_DEP = re.compile(
    r"""\.\s*add_(runtime_|development_)?dependency\s*\(?\s*(?:['"]([^'"]+)['"]|%q[<{(\[]([^>})\]]+)[>})\]])""")


def _parse_gemspec(text: str, path: str) -> Parsed:
    """``spec.add_dependency`` / ``add_runtime_dependency`` / ``add_development_dependency``."""
    out: Parsed = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        m = _GEMSPEC_DEP.search(line)
        if m:
            name = m.group(2) or m.group(3)
            scope = "dev" if m.group(1) == "development_" else "runtime"
            out.append((name, "rubygems", scope, _gem_versions(line, m.end())))
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
    "gemspec": _parse_gemspec,
}

_RUNTIME_OF_KIND = {
    "requirements": "Python", "pyproject": "Python", "setup.cfg": "Python", "setup.py": "Python",
    "pipfile": "Python", "package.json": "Node.js", "gemfile": "Ruby", "composer": "PHP",
    "pom": "JVM", "gradle": "JVM", "go.mod": "Go", "cargo": "Rust", "pubspec": "Dart",
    "gemspec": "Ruby",
}


def parse_manifest(path: str, text: str) -> List[Dependency]:
    """يحلل ملف اعتماديات واحداً إلى قائمة Dependency (يرفع استثناء عند ملف مشوَّه)."""
    kind = manifest_kind(path)
    if kind is None:
        return []
    example = _is_example_path(path)
    deps: List[Dependency] = []
    for item in _PARSERS[kind](text, path):
        name, eco, scope = item[0], item[1], item[2]
        deps.append(Dependency(
            name=normalize_name(name, eco),
            ecosystem=eco,
            scope="example" if example else scope,
            manifest=str(_posix(path)),
            specifier=item[3] if len(item) > 3 else "",
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
            counted = dep.scope in FRAMEWORK_SCOPES
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


# ---------------------------------------------------------------------------
# R-W2-002 — استخراج الاعتماديات ومديري الحزم
# ---------------------------------------------------------------------------
def project_dependencies(report: StackReport, scopes: Iterable[str] = COUNTED_SCOPES) -> List[str]:
    """الاعتماديات المباشرة التي يحتاجها المشروع ليعمل: أسماء مطبَّعة، فريدة، مرتبة.

    افتراضياً النطاقان ``runtime`` و``peer`` فقط ومن غير ملفات الأمثلة؛ dev/optional/build/
    indirect/example تبقى في ``dependency_records``.
    """
    wanted = set(scopes)
    return sorted({d.name for d in report.dependencies if d.scope in wanted})


def dependency_records(report: StackReport) -> List[Dict[str, object]]:
    """كل اعتمادية بكل حقولها (الاسم، النظام، النطاق، القيد، الملف) — مرتبة حتمياً."""
    return [asdict(d) for d in sorted(
        report.dependencies, key=lambda d: (d.ecosystem, d.name, d.scope, d.manifest, d.specifier))]


_LOCKFILE_MANAGERS = {
    "poetry.lock": "poetry", "uv.lock": "uv", "pdm.lock": "pdm", "Pipfile.lock": "pipenv",
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm", "bun.lockb": "bun", "bun.lock": "bun",
    "Gemfile.lock": "bundler", "composer.lock": "composer", "Cargo.lock": "cargo",
    "go.sum": "go", "pubspec.lock": "pub", "gradle.lockfile": "gradle",
}
_KIND_MANAGERS = {
    "requirements": "pip", "setup.py": "pip", "setup.cfg": "pip", "pipfile": "pipenv",
    "package.json": "npm", "go.mod": "go", "cargo": "cargo", "gemfile": "bundler",
    "gemspec": "bundler", "composer": "composer", "pom": "maven", "gradle": "gradle",
    "pubspec": "pub",
}


def detect_package_managers(paths: Iterable[str],
                            manifests: Optional[Mapping[str, Optional[str]]] = None) -> List[str]:
    """مديرو الحزم من ملفات الاعتماديات وملفات القفل (خارج المجلدات المُورَّدة والأمثلة).

    ``pyproject.toml`` يعني ``pip`` ما لم يكن فيه ``[tool.poetry]`` (→ ``poetry``) أو
    ``[tool.pdm]`` (→ ``pdm``)؛ ووجود ملف قفل يضيف مديره (yarn.lock → yarn …).
    """
    found: Dict[str, None] = {}
    for path in sorted(set(paths)):
        p = _posix(path)
        if any(part in SKIP_DIRS for part in p.parts[:-1]) or _is_example_path(path):
            continue
        if p.name in _LOCKFILE_MANAGERS:
            found.setdefault(_LOCKFILE_MANAGERS[p.name], None)
            continue
        kind = manifest_kind(path)
        if kind == "pyproject":
            text = (manifests or {}).get(path) or ""
            if re.search(r"^\[tool\.poetry", text, re.M):
                found.setdefault("poetry", None)
            elif re.search(r"^\[tool\.pdm", text, re.M):
                found.setdefault("pdm", None)
            else:
                found.setdefault("pip", None)
        elif kind in _KIND_MANAGERS:
            found.setdefault(_KIND_MANAGERS[kind], None)
    return sorted(found)


def detect_package_managers_at(root: "os.PathLike[str] | str") -> List[str]:
    """``detect_package_managers`` على مجلد في القرص (ملفات الاعتماديات + ملفات القفل)."""
    base = Path(root)
    if not base.is_dir():
        return []
    paths: List[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for fname in filenames:
            if fname in _LOCKFILE_MANAGERS or manifest_kind(fname) is not None:
                paths.append((Path(dirpath) / fname).relative_to(base).as_posix())
    return detect_package_managers(paths, read_manifests(base))


# ---------------------------------------------------------------------------
# R-W2-003 — وزن اللغات بعدد الأسطر والملفات واللغة الرئيسية الصحيحة
# ---------------------------------------------------------------------------
# امتدادات ملفات الكود → اللغة. مصدر واحد لكل المسارات (المسار الحي وrie
# والتحليل الحضاري ومحلل الذكاء وشريحة الاكتشاف)؛ الجداول القديمة فيها صارت
# واجهات تُحيل إلى هذا الجدول. اللغات هي التي تنمذجها الكواشف القائمة، بلا إضافات.
LANGUAGE_EXTENSIONS: Dict[str, Tuple[str, ...]] = {
    "Python": (".py",),
    "JavaScript": (".js", ".jsx", ".mjs", ".cjs"),
    "TypeScript": (".ts", ".tsx"),
    "Java": (".java",),
    "Go": (".go",),
    "Rust": (".rs",),
    "C": (".c", ".h"),
    "C++": (".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx"),
    "C#": (".cs",),
    "Ruby": (".rb",),
    "PHP": (".php",),
    "Swift": (".swift",),
    "Kotlin": (".kt", ".kts"),
    "Scala": (".scala", ".sbt"),
    "Dart": (".dart",),
    "R": (".r",),  # يشمل .R بالتطبيع الصغير لاحقاً
}

_LANGUAGE_OF_EXT: Dict[str, str] = {
    ext: lang for lang, exts in LANGUAGE_EXTENSIONS.items() for ext in exts}


@dataclass
class LanguageStat:
    """وزن لغة واحدة: عدد الملفات وعدد الأسطر (R-W2-003)."""
    language: str
    files: int = 0
    lines: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {"files": self.files, "lines": self.lines}


def _count_lines(text: str) -> int:
    """عدد الأسطر: أسطر \n زائد سطر أخير غير مُنهى إن وُجد."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def language_weights(files: Mapping[str, Optional[str]]) -> Dict[str, LanguageStat]:
    """وزن اللغات بعدد الأسطر والملفات (R-W2-003).

    ``files``: مسار → محتوى نصي (أو ``None`` إن تعذر قراءته، فيُحسب الملف بلا أسطر).
    المجلدات المُورَّدة (``SKIP_DIRS``) تُتجاهل كلياً: كود node_modules وvendor ليس
    كود المشروع. مجلدات الأمثلة والتوثيق تُحتسب: كودها كتبه صاحب المستودع.

    الترتيب حتمي: الأسطر تنازلياً، ثم الملفات تنازلياً، ثم الاسم أبجدياً؛ وهو نفسه
    ترتيب احتساب اللغة الرئيسية في ``primary_language``.
    """
    stats: Dict[str, LanguageStat] = {}
    for path in sorted(files):
        p = _posix(path)
        if any(part in SKIP_DIRS for part in p.parts[:-1]):
            continue
        lang = _LANGUAGE_OF_EXT.get(p.suffix.lower())
        if lang is None:
            continue
        stat = stats.setdefault(lang, LanguageStat(language=lang))
        stat.files += 1
        content = files[path]
        if content is not None and "\x00" not in content:
            stat.lines += _count_lines(content)
    return {stat.language: stat for stat in sorted(stats.values(),
                                                     key=lambda s: (-s.lines, -s.files, s.language))}


def primary_language(weights: Mapping[str, LanguageStat]) -> str:
    """اللغة الرئيسية: الأكثر أسطراً، ثم الأكثر ملفات، ثم الأبجدياً (حتمي)."""
    if not weights:
        return ""
    return min(weights.values(), key=lambda s: (-s.lines, -s.files, s.language)).language


def language_breakdown(files: Mapping[str, Optional[str]]) -> Dict[str, Dict[str, int]]:
    """``{language: {files, lines}}`` — حقل ``language_stats`` في كل DNA (R-W2-003)."""
    return {lang: stat.to_dict() for lang, stat in language_weights(files).items()}


def read_code_files(root: "os.PathLike[str] | str", max_bytes: int = 1_000_000) -> Dict[str, str]:
    """يقرأ ملفات الكود فقط من مجلد على القرص (يتخطى المجلدات المُورَّدة والروابط الرمزية)."""
    base = Path(root)
    out: Dict[str, str] = {}
    if not base.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for fname in sorted(filenames):
            if _LANGUAGE_OF_EXT.get(Path(fname).suffix.lower()) is None:
                continue
            full = Path(dirpath) / fname
            if full.is_symlink():
                continue
            try:
                if full.stat().st_size > max_bytes:
                    continue
                out[full.relative_to(base).as_posix()] = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return out


# ---------------------------------------------------------------------------
# R-W2-004 — نقاط الدخول وشجرة المجلدات والملفات المخفية ذات الصلة
# ---------------------------------------------------------------------------
# مجلدات مخفية تحمل معلومات مشروع حقيقية (CI/CD وإعدادات مستوى المستودع)؛ يُتجاهل
# الباقي (.git و.git الداخلية دائماً).
RELEVANT_HIDDEN_DIRS: Tuple[str, ...] = (".github", ".circleci", ".gitlab")
# ملفات مخفية ذات صلة ببناء المشروع وتشغيله؛ أي ملف بهذا الاسم في أي عمق مقبول.
RELEVANT_HIDDEN_FILES: Tuple[str, ...] = (
    ".gitignore", ".gitattributes", ".env.example", ".editorconfig", ".dockerignore",
    ".nvmrc", ".tool-versions", ".python-version", ".npmrc", ".prettierrc",
    ".eslintrc", ".eslintrc.json", ".eslintrc.yml", ".flake8", ".babelrc",
)


def _norm_path(path: "os.PathLike[str] | str") -> PurePosixPath:
    """مثل ``_posix`` لكن دون تجريد النقطة البادئة — ``.github`` يبقى ``.github`` (R-W2-004)."""
    return PurePosixPath(str(path).replace("\\", "/"))


def is_relevant_hidden(path: "os.PathLike[str] | str") -> bool:
    """هل هذا المسار ملفاً/مجلداً مخفياً ذا صلة بالمشروع (R-W2-004)؟

    ``.github`` ومثيلاته من مجلدات الـ CI، والملفات مثل ``.gitignore`` و``.env.example``
    ليست مخلفات: إنها تكوين المشروع. ما عدا ذلك من المخفي يُتجاهل (``.git`` دائماً).
    """
    p = _norm_path(path)
    if not p.parts or p.name == ".git":
        return False
    if p.parts[0] in RELEVANT_HIDDEN_DIRS:
        return True
    return p.name in RELEVANT_HIDDEN_FILES


# ملفات الدخول الاصطلاحية باسمها، في الجذر أو مجلدات الدخول المألوفة.
_ENTRY_BASENAMES: Tuple[str, ...] = (
    "main.py", "app.py", "manage.py", "cli.py", "run.py", "setup.py",
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "app.js",
    "main.go", "Makefile", "Dockerfile",
)
_ENTRY_ROOT_DIRS: Tuple[str, ...] = ("", "src", "bin", "scripts")


def _manifest_entry_points(manifests: Optional[Mapping[str, Optional[str]]]) -> List[str]:
    """نقاط الدخول المعلنة في الملفات: pyproject [project.scripts] وpackage.json main/bin."""
    out: List[str] = []
    if not manifests:
        return out
    for path, content in sorted(manifests.items()):
        if not content:
            continue
        name = os.path.basename(path)
        try:
            if name == "pyproject.toml":
                data = _toml.loads(content) if _toml is not None else {}
                scripts = ((data.get("project") or {}).get("scripts") or {})
                out.extend(f"pyproject.toml:scripts:{k}" for k in sorted(scripts))
            elif name == "package.json":
                data = json.loads(content)
                main = data.get("main")
                if isinstance(main, str):
                    out.append(f"package.json:main:{main}")
                bins = data.get("bin")
                if isinstance(bins, dict):
                    out.extend(f"package.json:bin:{k}" for k in sorted(bins))
                elif isinstance(bins, str):
                    out.append(f"package.json:bin:{bins}")
        except (ValueError, TypeError):
            continue
    return sorted(set(out))


def detect_entry_points(paths: Iterable[str],
                        manifests: Optional[Mapping[str, Optional[str]]] = None) -> List[str]:
    """نقاط الدخول: ملفات اصطلاحية + معلن في الملفات (R-W2-004).

    الاصطلاح: ملف باسم دخول معروف (main.py, index.js, …) في الجذر أو ``src`` أو
    ``bin`` أو ``scripts``، أو ``cmd/<name>/main.go``، أو ``src/main.rs`` أو ``src/bin/*.rs``.
    والمعمول: ``pyproject.toml`` [project.scripts] و``package.json`` main/bin — تُعاد
    كأسهم ``manifest:field:name`` لأنها تصريح لا ملف. الحتمية: قائمة مرتبة بلا تكرار.
    """
    out: List[str] = []
    for raw in paths:
        p = _norm_path(raw)
        if not p.parts:
            continue
        name = p.name
        parent = p.parts[-2] if len(p.parts) >= 2 else ""
        if name in _ENTRY_BASENAMES and parent in _ENTRY_ROOT_DIRS:
            out.append(p.as_posix())
        elif name == "main.go" and len(p.parts) >= 3 and p.parts[-3] == "cmd":
            out.append(p.as_posix())
        elif name == "main.rs" and len(p.parts) == 2 and p.parts[0] == "src":
            out.append(p.as_posix())
        elif p.suffix == ".rs" and len(p.parts) == 3 and p.parts[0] == "src" and p.parts[1] == "bin":
            out.append(p.as_posix())
    out.extend(_manifest_entry_points(manifests))
    return sorted(set(out))


def directory_tree(paths: Iterable[str], max_depth: int = 3, limit: int = 200,
                    dir_paths: Optional[Iterable[str]] = None) -> List[str]:
    """شجرة المجلدات بعمق قابل للضبط (R-W2-004).

    ``paths``: كل المسارات (ملفات ومجلدات). ``dir_paths``: المجلدات صراحةً (إن عُرفت)
    — لأن الاسم وحده لا يكفي للتمييز (``Makefile`` ملف و``src`` مجلد، و``.github``
    مجلد رغم نقطته). إن غابت تُستنتج المجلدات بما لا له لاحقة ولا نقطة.

    المجلدات فريدة حتى ``max_depth``، بلا المُورَّد (``SKIP_DIRS``)، مرتبة وبحد ``limit``.
    ``max_depth=1`` يعادل الطبقة العليا فقط.
    """
    if max_depth < 1:
        return []
    dirs = set()
    known_dirs = set()
    if dir_paths is not None:
        known_dirs = {_norm_path(d).as_posix() for d in dir_paths}
    for raw in paths:
        p = _norm_path(raw)
        posix = p.as_posix()
        is_dir = posix in known_dirs or (
            dir_paths is None and not p.suffix and "." not in p.name)
        parts = p.parts if is_dir else p.parts[:-1]
        for i in range(1, min(len(parts), max_depth) + 1):
            if any(part in SKIP_DIRS for part in parts[:i]):
                break
            dirs.add("/".join(parts[:i]))
    return sorted(dirs)[:limit]


# لواحق ملفات التكوين وأسماؤها المعروفة (بدون مطابقة جزئية للنص).
CONFIG_SUFFIXES: Tuple[str, ...] = (".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")
CONFIG_NAMES: Tuple[str, ...] = (
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "Pipfile",
    "package.json", "Gemfile", "go.mod", "Cargo.toml", "composer.json", "pubspec.yaml",
    "pom.xml", "build.gradle", "build.gradle.kts", "Makefile", "CMakeLists.txt",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "tsconfig.json",
    "webpack.config.js", "vite.config.js", ".env.example", "procfile",
    ".gitignore", ".editorconfig", ".dockerignore", ".nvmrc", ".tool-versions",
    ".python-version",
)


_CONFIG_NAMES_LOWER = {c.lower() for c in CONFIG_NAMES}


def detect_config_files(paths: Iterable[str], limit: int = 20) -> List[str]:
    """ملفات التكوين: مطابقة لاحقة أو اسم صريح — لا مطابقة جزئية (R-W2-004).

    القاعدة القديمة كانت ``ext in path`` فكان "docs/package.json.md" يُحسب ملف
    package.json. الآن: اللاحقة أو الاسم المعروف، بلا المُورَّد، مرتبة وبحد ``limit``.
    """
    out: List[str] = []
    for raw in paths:
        p = _norm_path(raw)
        if any(part in SKIP_DIRS for part in p.parts[:-1]):
            continue
        if p.name.lower() in _CONFIG_NAMES_LOWER or p.suffix.lower() in CONFIG_SUFFIXES:
            out.append(p.as_posix())
    return sorted(set(out))[:limit]
