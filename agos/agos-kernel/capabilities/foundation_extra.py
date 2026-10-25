"""Foundation Capabilities 14-20 — تنفيذ حقيقي (R-W2-007).

قبل هذا البند كانت كل قدرة هنا تعيد نتائج ثابتة فارغة — «نظيفة» بلا فحص. عقد هذا
الملف صار: **لا نتيجة إيجابية بلا فحص** — كل حقل مشتق من محتوى فعلي، وكل نتيجة
تحمل دليلها (ملف/سطر/عبارة/عدد)، وكل فحص تعذر يُعلن حالته بدل أن يتحول إلى
«آمن» أو «متوافق».

القدرات السبع (بنفس أسماء الأصناف والمفاتيح القديمة — G2):

| القدرة | ما تفحصه فعلاً |
|---|---|
| SecurityScan | أسرار محتملة بأنماط مميزة (مفتاح AWS/GitHub/Slack/مفتاح خاص/JWT…) بمسح قرصي محدود يشمل `.env`، مع دليل منقّح (لا يُعاد السطر الخام أبداً)، وفحص OSV للإصدارات المثبتة بدقة فقط |
| LicenseAnalysis | ترخيص المشروع من نص LICENSE (عبارات SPDX قياسية) منفصلاً عن الترخيص المعلن في الملفات، مع فحص التعارض |
| DocumentationAnalysis | تغطية docstrings لعناصر Python الفعلية (بسط/مقام)، ونسبة ملفات التوثيق منفصلة، والوثائق المتوقعة الغائبة |
| ConfigurationAnalysis | ملفات التكوين (من stack_detection)، والبيئات بأسماء كاملة لا بجزء كلمة، وأخطاء تحليل JSON حقيقية |
| InfrastructureAnalysis | Docker/Kubernetes/Terraform من المحتوى، ومزودو السحابة كأدلة اعتماد (SDK) منفصلة عن أدلة البنية |
| RepositoryDNAGeneration | لغات وأطر ومديرو حزم من stack_detection، وبصمة sha256 لحقائق مرتبة (ثابتة مهما اختلف ترتيب الملفات) |
| EngineeringKnowledgeExtraction | نتائج مأخوذة من مخرجات القدرات الأخرى بالذات، والفجوات تُمرَّر كما هي ولا تتحول إلى اطمئنان |

مسار البيانات: كل قدرة تقبل ``{"url": ...}`` (استنساخ + قراءة، مع تنظيف مضمون)،
أو ``{"repo_path": ...}`` (قراءة بلا تنظيف)، أو ``{"snapshot": ...}`` (لقطة
جاهزة: RepositorySnapshot أو قاموس)، أو ``{"files": {path: content}}``. التمييز
ملزم: محتوى ``None`` يعني «لم يُقرأ»، والسلسلة الفارغة تعني «قُرئ ووجد فارغاً».

فحص OSV: إصدارات مثبتة بدقة فقط (القيود النطاقية تُسجل في unresolved_dependencies
ولا تُفحص)، وفشل الفحص يُعلن (osv_status) ولا يخفض الخطورة أبداً.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from interfaces import ICapability

__all__ = [
    "SecurityScanCapability",
    "LicenseAnalysisCapability",
    "DocumentationAnalysisCapability",
    "ConfigurationAnalysisCapability",
    "InfrastructureAnalysisCapability",
    "RepositoryDNAGenerationCapability",
    "EngineeringKnowledgeExtractionCapability",
    "osv_query_batch",
    "scan_secrets",
    "spdx_license_of",
    "SECRET_RULES",
]


# ---------------------------------------------------------------------------
# مسار البيانات: تعليم لقطة موحد لكل القدرات
# ---------------------------------------------------------------------------
@dataclass
class _FileView:
    """ملف واحد كما تراه القدرة — content=None تعني «لم يُقرأ» لا «فارغ»."""
    path: str
    content: Optional[str] = None
    is_dir: bool = False
    size: int = 0


class _Repo:
    """قرص مستودع + لقطته — يُنشأ من url/repo_path/snapshot/files.

    ``owns_root``: هل نحن من استنسخ (وعلينا التنظيف في finally)؟
    """

    def __init__(self, root: Optional[str], files: List[_FileView], owns_root: bool):
        self.root = root
        self.files = files
        self.owns_root = owns_root

    def contents(self) -> Dict[str, Optional[str]]:
        """{المسار: المحتوى أو None} للملفات غير المجلدية — المفتاح للفحوص النصية."""
        return {f.path: f.content for f in self.files if not f.is_dir}

    def cleanup(self) -> None:
        # ملكية معلنة (المادة 4 — الشريحة 0100): حذف الجذر المملوك وحده —
        # عقد الاستنساخ يسلم ملكية المسار لا أصله، فالوالد (أياً كان اسمه أو
        # فراغه) لا يُمس من جانب المستهلك: لا استنتاج ملكية من اسم أو فراغ
        if self.owns_root and self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root, ignore_errors=True)


def _files_from_nodes(nodes: Iterable[Any]) -> List[_FileView]:
    out: List[_FileView] = []
    for n in nodes:
        if isinstance(n, dict):
            out.append(_FileView(path=str(n.get("path", "")),
                                 content=n.get("content"),
                                 is_dir=bool(n.get("is_dir", False)),
                                 size=int(n.get("size", 0) or 0)))
        else:
            out.append(_FileView(path=str(getattr(n, "path", "")),
                                 content=getattr(n, "content", None),
                                 is_dir=bool(getattr(n, "is_dir", False)),
                                 size=int(getattr(n, "size", 0) or 0)))
    return out


def _acquire(input_data: Any, provider=None) -> _Repo:
    """توحيد المدخلات الأربعة إلى _Repo — استنساخ مُنظَّف عند الفشل دائماً."""
    if not isinstance(input_data, dict):
        # عقد قديم: قائمة ملات مباشرة، أو RepositorySnapshot نفسه
        if isinstance(input_data, list):
            return _Repo(None, _files_from_nodes(input_data), owns_root=False)
        if hasattr(input_data, "files"):
            return _Repo(getattr(input_data, "root_path", None),
                        _files_from_nodes(input_data.files), owns_root=False)
        raise ValueError("input must be a dict, a file list, or a RepositorySnapshot")

    if "snapshot" in input_data:
        snap = input_data["snapshot"]
        if isinstance(snap, dict):
            files = _files_from_snapshot_dict(snap)
            root = snap.get("root_path")
            return _Repo(root, files, owns_root=False)
        if hasattr(snap, "files"):
            return _Repo(getattr(snap, "root_path", None),
                        _files_from_nodes(snap.files), owns_root=False)
        return _Repo(None, _files_from_nodes(snap), owns_root=False)

    if "files" in input_data:
        raw = input_data["files"]
        if isinstance(raw, dict):
            files = [_FileView(path=str(p), content=c) for p, c in raw.items()]
        elif isinstance(raw, list):
            files = _files_from_nodes(raw)
        else:
            raise ValueError("files must be a mapping or a list")
        return _Repo(input_data.get("root_path"), files, owns_root=False)

    url = input_data.get("url")
    repo_path = input_data.get("repo_path") or input_data.get("path")
    if url:
        # المادة 4 (الشريحة 0100): الاستنساخ والقراءة بعقدي المهارة بالمزوّد
        # المختار — لا استدعاء مباشر لclone_safety ولا لطريقة صنف المزوّد
        root = _clone_via_contract(url, input_data.get("branch"), provider)
        try:
            return _Repo(root,
                         _walk_for_capabilities(root, provider=provider),
                         owns_root=True)
        except BaseException:
            _safe_cleanup(root)
            raise
    if repo_path:
        return _Repo(repo_path,
                     _walk_for_capabilities(repo_path, provider=provider),
                     owns_root=False)
    raise ValueError("input needs one of: url, repo_path, snapshot, files")


def _files_from_snapshot_dict(snap: Dict[str, Any]) -> List[_FileView]:
    """لقطة قاموسية: ``files`` قائمة عقد أو قاموس مسار←محتوى (R-W2-007)."""
    raw = snap.get("files", [])
    if isinstance(raw, dict):
        return [_FileView(path=str(p), content=c) for p, c in raw.items()]
    return _files_from_nodes(raw)


def _fallback_provider():
    """الاحتياط المعلن عند غياب المزوّد المختار (مدخل execute العام) — إنشاء
    الصنف الخرساني تبعية معلنة لا خفية (حد معلن في صف المادة 4 — لا يغلق الصف)."""
    from providers import LocalRepositoryProvider
    return LocalRepositoryProvider()


def _clone_via_contract(url: str, branch, provider) -> str:
    """الاستنساخ عبر عقد المهارة المعلن بالمزوّد المختار — لا استدعاء مباشر
    لـ``clone_safety`` من المستهلك. دلالة ``branch=None`` محفوظة كما هي
    (git يختار الفرع الافتراضي — لا استبدال بـ``"main"``)."""
    from providers import CloneRepositoryInput
    prov = provider if provider is not None else _fallback_provider()
    return prov.execute("CloneRepository",
                        CloneRepositoryInput(url, branch,
                                             require_metadata=False)).path


def _safe_cleanup(root: str) -> None:
    """حذف الجذر المملوك وحده — لا حذف لأب كامل قد يضم جاراً غير مملوك
    (عقد الاستنساخ يسلم ملكية المسار لا أصله)."""
    shutil.rmtree(root, ignore_errors=True)


def _walk_for_capabilities(root: str, max_bytes: int = 1_000_000,
                           provider=None) -> List[_FileView]:
    """قراءة ملفات المستودع للقدرات — بلا استنساخ، عبر عقد مهارة المسح
    بالمزوّد المختار (لا استدعاء مباشر لطريقة الصنف — المادة 4).

    يشمل الملفات المخفية ذات الصلة (R-W2-004) ويستثني `.git` والروابط الرمزية
    (R-W2-005). محتوى ``None`` = لم يُقرأ (حجم/ثنائي) — لا يساوي الفارغ أبداً.
    عقد المسح لا يشترط ميتاداتا (ولا origin) — المدخلات المقبولة محفوظة
    (مستودع محلي بلا remote يبقى مقروءاً).
    """
    from providers import WalkRepositoryInput
    prov = provider if provider is not None else _fallback_provider()
    nodes = prov.execute(
        "WalkRepository", WalkRepositoryInput(root)).files
    return _files_from_nodes(nodes)


# ---------------------------------------------------------------------------
# CAPABILITY-000014: SecurityScan — أسرار محتملة + فحص OSV
# ---------------------------------------------------------------------------
SECRET_RULES: Tuple[Tuple[str, str, str], ...] = (
    # (id, وصف, النمط) — أنماط مميزة عالية الثقة، تطبق على كل ملف نصي
    ("aws-access-key", "AWS access key ID (AKIA…)", r"\bAKIA[0-9A-Z]{16}\b"),
    ("github-token", "GitHub personal access token", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ("slack-token", "Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("google-api-key", "Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("private-key", "Private key block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("jwt", "Hard-coded JWT", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."),
)

# القاعدة العامة: إسناد سر في ملفات التكوين/البيئة (بما فيها .env.example — سر حقيقي
# فيها مشكلة أيضاً) — نتيجتها «سر محتمل» دائماً لا اعتماد مُتحقق من صلاحيته.
_GENERIC_SECRET = re.compile(
    r"(?i)^\s*(?:password|passwd|secret|api[_-]?key|apikey|token|access[_-]?key)"
    r"\s*[:=]\s*['\"]?([^\s'\"]{8,})['\"]?\s*$")
_PLACEHOLDER = re.compile(
    r"(?i)^(\$\{[^}]*\}|<[^>]*>|\*+|x{3,}|changeme|change-me|example|placeholder"
    r"|your[_-][a-z]+|todo|fixme|redacted|dummy|sample)[^ ]*$")
_ENVISH = re.compile(r"(?i)(^|/|\.)(\.?env|config|settings|credentials?|secrets?)")
_SECRET_FILENAMES = {".env", ".env.local", ".env.production", ".env.development",
                     ".env.live", ".netrc", ".npmrc_auth", ".pypirc", ".git-credentials"}


def _redact(value: str) -> str:
    """دليل منقّح: أول 4 محارف ثم عدد المحارف — لا يُعاد السر الخام أبداً."""
    return f"{value[:4]}…({len(value)} chars)"


def scan_secrets(root: Optional[str], files: Optional[Dict[str, Optional[str]]] = None,
                 max_bytes: int = 1_000_000) -> Dict[str, Any]:
    """مسح الأسرار: قرصي مباشر عند توفر root (يشمل .env)، أو على المحتويات المعطاة.

    كل نتيجة: ملف/سطر/قاعدة/قيمة منقّحة — ولا شيء خام. النتيجة «سر محتمل»:
    تطابق نمط لا تحقق من صلاحية الاعتماد.
    """
    findings: List[Dict[str, Any]] = []
    scanned = 0
    unreadable = 0

    if root and os.path.isdir(root):
        base = os.path.realpath(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d != ".git" and not os.path.islink(os.path.join(dirpath, d))]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if os.path.islink(full):
                    continue
                try:
                    if os.path.getsize(full) > max_bytes:
                        unreadable += 1
                        continue
                    with open(full, "rb") as fh:
                        raw = fh.read()
                except OSError:
                    unreadable += 1
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    unreadable += 1
                    continue
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                scanned += 1
                findings.extend(_scan_text(rel, text))
    elif files:
        for path, content in sorted(files.items()):
            if content is None:
                unreadable += 1
                continue
            scanned += 1
            findings.extend(_scan_text(path, content))

    return {"findings": findings, "scanned": scanned, "unreadable": unreadable}


def _scan_text(path: str, text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for rule_id, desc, pattern in SECRET_RULES:
            m = re.search(pattern, line)
            if m:
                out.append({"file": path, "line": i, "rule": rule_id,
                            "description": desc, "evidence": _redact(m.group(0))})
                break  # قاعدة واحدة لكل سطر تكفي — لا تضخيم العدد
        if _ENVISH.search(path) or os.path.basename(path) in _SECRET_FILENAMES:
            m = _GENERIC_SECRET.match(line)
            if m and not _PLACEHOLDER.match(m.group(1)):
                out.append({"file": path, "line": i, "rule": "generic-secret",
                            "description": "Potential hard-coded secret in config/env file",
                            "evidence": _redact(m.group(1))})
    return out


# --- OSV (https://api.osv.dev) — إصدارات مثبتة بدقة فقط ------------------------
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_OSV_ECOSYSTEMS = {"pypi": "PyPI", "npm": "npm", "go": "Go", "cargo": "crates.io",
                   "rubygems": "RubyGems", "composer": "Packagist", "maven": "Maven",
                   "pub": "Pub"}
_EXACT_VERSION = re.compile(r"\d+(\.\d+){0,3}(-[0-9A-Za-z.]+)?(\+[0-9A-Za-z.-]+)?")


_PIN_RULES: Dict[str, Tuple[str, ...]] = {
    # نطاق يميز المثبت بدقة من القيد — وعياً بالنظام البيئي
    "pypi": ("==",),            # pip يحتاج مانع للتثبيت، والمجرد من الاسم ليس تثبيتاً
    "npm": ("exact",),          # 1.2.3 في npm دقيق؛ ^/~/>/< نطاق
    "go": ("exact",),           # go.mod يتطلب إصداراً دقيقاً
    "rubygems": ("exact",),     # Gemfile: 5.0 دقيق؛ ~> نطاق
    "cargo": (),                # في Cargo.toml الـ 1.2.3 يعني مطالقاً ^1.2.3 — ليس ثبيتاً (الدقيق في Cargo.lock)
    "maven": ("exact",),
    "composer": ("exact",),
    "pub": ("exact",),
}


def pinned_version(specifier: str, ecosystem: str = "") -> Optional[str]:
    """الإصدار المثبت بدقة من القيد، أو None — وعياً بالنطام البيئي.

    القواعد: ``==x`` دقيقة في كل نطام؛ ومعاملات النطاق (~ ^ > < *) ليست ثبيتاً؛ والإصدار المجرد ليس تثبيتاً إلا في النطام الذي دلالته على الدقة —
    وفي Cargo.toml الـ ``1.2.3`` يعني مطالقاً ``^1.2.3`` (ليس ثبيتاً؛ الدقيق في Cargo.lock)، وفي pypi الـ ``flask`` بلا قيد يعني أي إصدار.
    """
    spec = (specifier or "").strip()
    if not spec or "${" in spec or "*" in spec or "," in spec:
        return None
    if spec.startswith("=="):
        version = spec[2:].strip()
    else:
        if spec[:1] in "~^<>=":
            return None
        # إصدار مجرد: دقيق فقط في النطامات المدينة للدقة
        if "exact" not in _PIN_RULES.get(ecosystem, ("exact",)):
            return None
        version = spec
    if version.startswith("v"):
        version = version[1:]
    return version if _EXACT_VERSION.fullmatch(version) else None


def osv_query_batch(queries: List[Dict[str, Any]], *,
                    endpoint: str = OSV_BATCH_URL, timeout: int = 30) -> List[Dict[str, Any]]:
    """فحص دفعي في OSV — يرسل أسماء الحزم وإصداراتها فقط، لا محتوى ولا أسرار.

    تعيد النتائج مرتبة على نفس ترتيب الاستعلامات؛ كل نتيجة ``{"vulns": [...]}``
    أو أقرب لها — الشدة والتفاصيل تُؤخذ مما تعيده الواجهة فقط، لا استنتاج.
    """
    import urllib.request
    payload = json.dumps({"queries": queries}).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return list(body.get("results", []))


class SecurityScanCapability(ICapability):
    """Scan a repository for security issues — for real (R-W2-007)."""

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            from stack_detection import dependency_records, detect_stack

            scan = scan_secrets(repo.root, repo.contents() if repo.root is None else None)
            secrets = scan["findings"]

            # الاعتماديات: من الملفات المقروءة فعلاً — لا شيء بلا دليل
            stack = detect_stack(repo.contents())
            records = dependency_records(stack)
            pins: List[Dict[str, Any]] = []
            unresolved: List[Dict[str, str]] = []
            for rec in records:
                ecosystem = str(rec.get("ecosystem", ""))
                pin = pinned_version(str(rec.get("specifier", "")), ecosystem)
                osv_eco = _OSV_ECOSYSTEMS.get(ecosystem)
                if pin and osv_eco:
                    pins.append({"package": {"name": rec.get("name"), "ecosystem": osv_eco},
                                 "version": pin})
                else:
                    unresolved.append({"name": str(rec.get("name")),
                                       "specifier": str(rec.get("specifier", ""))})

            vulnerabilities, osv_status, osv_error = self._osv(pins, input_data)

            # أخطاء تحليل ملفات الاعتماديات وملفات لم تُقرأ — فحص جزئي لا نظيف
            stack_errors = sorted(stack.errors) if stack.errors else []
            risk = self._risk(secrets, vulnerabilities, osv_status, unresolved,
                              scan["unreadable"], stack_errors)
            return {
                "capability": self.name,
                "secrets": secrets,
                "secrets_found": len(secrets),
                "vulnerabilities": vulnerabilities,
                "risk_level": risk,
                "osv_status": osv_status,          # completed | failed | skipped_no_pins
                "osv_error": osv_error,
                "unresolved_dependencies": unresolved,
                "scanned_files": scan["scanned"],
                "unreadable_files": scan["unreadable"],
                "manifest_parse_errors": stack_errors,
            }
        finally:
            repo.cleanup()

    def _osv(self, pins: List[Dict[str, Any]], input_data: Dict[str, Any]
             ) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
        if not pins:
            return [], "skipped_no_pins", None
        query = input_data.get("osv_query") or osv_query_batch
        try:
            results = query(pins)
            # الاستجابة قائمة مطابقة للاستعلامات — أقصر منها فحص جزئي لا نجاه
            if not isinstance(results, list):
                return [], "failed", f"malformed OSV response: {type(results).__name__}"
            if len(results) != len(pins):
                return [], "partial", \
                    f"OSV returned {len(results)} results for {len(pins)} queries"
            out: List[Dict[str, Any]] = []
            for pin, result in zip(pins, results):
                if not isinstance(result, dict):
                    return [], "failed", "malformed OSV result entry"
                for vuln in (result.get("vulns") or []):
                    if not isinstance(vuln, dict):
                        continue
                    out.append({
                        "dependency": pin["package"]["name"],
                        "version": pin["version"],
                        "osv_id": vuln.get("id"),
                        "summary": vuln.get("summary"),   # قد تكون None — لا تُخترع
                    })
            return out, "completed", None
        except Exception as exc:  # فشل الفحص يُعلن ولا يخفض الخطورة أبداً
            return [], "failed", str(exc)[:200]

    @staticmethod
    def _risk(secrets: List[Dict], vulns: List[Dict], osv_status: str,
              unresolved: List[Dict], unreadable: int = 0,
              manifest_errors: Optional[List[str]] = None) -> str:
        if secrets or vulns:
            return "high"
        if (osv_status in ("failed", "partial") or unresolved or unreadable
                or (manifest_errors or [])):
            return "medium"          # فحص لم يكتمل/قيود لم تُفحص — ليست «آمنة»
        if osv_status == "completed":
            return "low"             # فُحص كل شيء ولم يُوجد شيء — وحدها تستحق low
        return "unknown"             # لم يُفحص شيء — لا ادعاء أمان

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "SecurityScan"
    version = "1.0.0"
    description = "Scans for potential secrets and known vulnerabilities (OSV)"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000015: License — SPDX من نص LICENSE منفصلاً عن المعلن
# ---------------------------------------------------------------------------
# عبارات قياسية من نصوص SPDX الرسمية — أول تطابق يفوز، والأدق أولاً.
# عبارات مميزة من النصوص القياسية — لا توقف على التفاف الأسطر (تمييز BSD-2/3 ببند المنع لا بسطر، وGPL بعبارة الإصدار المحددة لا بعنوان النسخة)
_SPDX_PHRASES: Tuple[Tuple[str, str], ...] = (
    ("MIT", "Permission is hereby granted, free of charge, to any person obtaining a copy"),
    ("Apache-2.0", "Apache License\nVersion 2.0, January 2004"),
    ("Apache-2.0", "Apache License\n                           Version 2.0, January 2004"),
    ("AGPL-3.0-only", "GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("MPL-2.0", "Mozilla Public License\nVersion 2.0"),
    ("MPL-2.0", "Mozilla Public License, Version 2.0"),
    ("ISC", "Permission to use, copy, modify, and/or distribute this software for any purpose"),
    ("CC0-1.0", "To the extent possible under law, the author(s) have dedicated all copyright"),
    ("Unlicense", "This is free and unencumbered software released into the public domain"),
)
# عائلة BSD: الفارق بين 2 و3 بند المنع المعروف؛ وعائلة GPL: الـ or-later
_BSD_CLAUSE = "Neither the name of the copyright holder nor the names of its contributors may be used"
_BSD_INTRO = "Redistribution and use in source and binary forms, with or without modification"
_GPL_INTRO = re.compile(r"GNU GENERAL PUBLIC LICENSE\s+\n?\s*Version (\d+)", re.M)
_GPL_OR_LATER = "or (at your option) any later version"
_LICENSE_FILE = re.compile(r"(?i)^(license|licence|copying|copyright|notice)([.\-_]?\w+)?$")
_SPDX_ID = re.compile(r"(?i)^(mit|apache-2\.0|bsd-2-clause|bsd-3-clause|gpl-2\.0-only|"
                      r"gpl-3\.0-only|gpl-2\.0-or-later|gpl-3\.0-or-later|"
                      r"agpl-3\.0-only|mpl-2\.0|isc|cc0-1\.0|unlicense)$")


def spdx_license_of(text: str) -> Tuple[str, str]:
    """(معرف SPDX أو "unknown"، العبارة الدليلية) — من نص الترخيص فقط.

    صيغة SPDX الصريحة (``SPDX-License-Identifier: X``) أولاً إن وُجدت في النص.
    """
    explicit = re.search(r"SPDX-License-Identifier:\s*([^\s\n]+)", text)
    if explicit and _SPDX_ID.match(explicit.group(1).strip()):
        return explicit.group(1).strip(), f"SPDX-License-Identifier: {explicit.group(1).strip()}"
    for spdx_id, phrase in _SPDX_PHRASES:
        if phrase in text:
            return spdx_id, phrase
    if _BSD_INTRO in text:
        if _BSD_CLAUSE in text:
            return "BSD-3-Clause", _BSD_CLAUSE
        return "BSD-2-Clause", _BSD_INTRO
    gpl = _GPL_INTRO.search(text)
    if gpl:
        suffix = "-or-later" if _GPL_OR_LATER in text else "-only"
        return f"GPL-{gpl.group(1)}.0{suffix}", gpl.group(0).replace("\n", " ")
    return "unknown", ""


class LicenseAnalysisCapability(ICapability):
    """Analyze repository licensing — declared vs detected, separately (R-W2-007)."""

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            contents = repo.contents()
            # 1) الترخيص من نص الملف — كل المرشحين يُفحصون، والمعروف منهم مفضلًا
            # (ملف COPYING غير معروف لا يحجب ترخيص LICENSE المعروف)
            license_file, detected, evidence = None, "unknown", ""
            candidates: List[Tuple[str, str]] = []
            license_candidates: List[str] = []
            for path in sorted(contents):
                if _LICENSE_FILE.match(os.path.basename(path)) and contents[path]:
                    candidates.append((path, spdx_license_of(contents[path])))
            if candidates:
                known = [c for c in candidates if c[1][0] != "unknown"]
                license_candidates = [c[0] for c in candidates]
                chosen = None
                for cand in known:
                    if os.path.basename(cand[0]).upper().startswith("LICENSE"):
                        chosen = cand
                        break
                if chosen is None and known:
                    chosen = known[0]
                if chosen is None:
                    chosen = candidates[0]
                license_file = chosen[0]
                detected, evidence = chosen[1]
            # 2) الترخيص المعلن في ملفات المشروع نفسه (لا اعتمادياته)
            declared, declaration_file = self._declared(contents)
            mismatch = bool(declared and detected not in ("unknown",)
                            and declared.lower() not in detected.lower()
                            and detected.lower() not in declared.lower())
            return {
                "capability": self.name,
                "license": detected,               # المستدل من النص
                "license_file": license_file,
                "license_candidates": license_candidates,
                "evidence": evidence or None,
                "declared_license": declared,      # المعلن في package.json/pyproject
                "declaration_file": declaration_file,
                "mismatch": mismatch,
                # تراخيص الاعتماديات لا تُجمع من هذه الملفات أصلاً (ترخيص المشروع
                # فيها ليس ترخيص اعتمادياته) — تُعلن حالتها بدل ادعاء قائمة فارغة
                "dependency_licenses": [],
                "dependency_licenses_status": "not_collected",
                "compatible": None,                # غير مفحوص — لا افتراض توافق
            }
        finally:
            repo.cleanup()

    @staticmethod
    def _declared(contents: Dict[str, Optional[str]]) -> Tuple[Optional[str], Optional[str]]:
        for path in sorted(contents):
            base = os.path.basename(path)
            text = contents[path]
            if not text:
                continue
            if base == "package.json":
                try:
                    data = json.loads(text)
                except (ValueError, TypeError, AttributeError):
                    continue
                if not isinstance(data, dict):
                    continue   # JSON صالح نحويًا لكنه قائمة — ليس كائن المشروع
                lic = data.get("license")
                if isinstance(lic, str) and lic.strip():
                    return lic.strip(), path
            elif base == "pyproject.toml":
                # TOML فعلي — التعبير المنطلق يمكن أن يكون داخل [tool.*] لا في [project]
                try:
                    import tomllib
                    data = tomllib.loads(text)
                except (ValueError, ImportError):
                    continue
                project = data.get("project")
                if not isinstance(project, dict):
                    continue
                lic = project.get("license")
                if isinstance(lic, str) and lic.strip():
                    return lic.strip(), path
                if isinstance(lic, dict) and isinstance(lic.get("text"), str):
                    return lic["text"].strip(), path
        return None, None

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "LicenseAnalysis"
    version = "1.0.0"
    description = "Detects the project license (SPDX) from text and declarations"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000016: Documentation — تغطية docstrings فعلية
# ---------------------------------------------------------------------------
_EXPECTED_DOCS = ("README", "LICENSE", "CONTRIBUTING", "CHANGELOG")


def _docstring_stats(path: str, text: str) -> Tuple[int, int]:
    """(الموثّق، الكل) لعناصر Python العامة؛ وَ``None`` إن كان الملف معطوباً نحوياً.

    النطاق المعلن: دوال وأصناف على مستوى الوحدة وطرق الأصناف المباشرة؛ أما الدوال المتداخلة (داخل دالة) فتفصيل تنفيذي لا يُحصى.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return 0, 0
    documented, total = 0, 0

    def count(node: ast.AST) -> None:
        nonlocal documented, total
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not child.name.startswith("_"):
                    total += 1
                    if ast.get_docstring(child):
                        documented += 1
                if isinstance(child, ast.ClassDef):
                    count(child)      # طرق الصنف فقط
                # دالة متداخلة داخل دالة: تفصيل تنفيذي — لا تُحصى
            else:
                count(child)

    count(tree)
    return documented, total


class DocumentationAnalysisCapability(ICapability):
    """Analyze documentation coverage — measured, not asserted (R-W2-007)."""

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            contents = repo.contents()
            paths = [p for p in contents if not os.path.basename(p).startswith(".git/")]
            root_names = {os.path.basename(p) for p in paths
                          if "/" not in p.replace("\\", "/")}

            has_readme = any(n.upper().startswith("README") for n in root_names)

            # doc_coverage: تغطية docstrings لعناصر Python العامة — قياس محدد بنطاقه
            documented = total = 0
            python_parse_errors: List[str] = []
            for path, text in contents.items():
                if path.endswith(".py"):
                    if text is None:
                        continue      # لم يُقرأ — يعلق في الفجوة لا يُنسق من المقام
                    try:
                        ast.parse(text)
                    except (SyntaxError, ValueError):
                        python_parse_errors.append(path)   # معطوب: يعلق من المقام — لا يرفع التغطية صامتاً
                    d, t = _docstring_stats(path, text)
                    documented += d
                    total += t
            doc_coverage = round(documented / total, 3) if total else 0.0

            # نسبة ملفات التوثيق إلى ملفات الشيفرة — مقياس منفصل باسمه الصادق
            doc_files = [p for p in paths if p.endswith((".md", ".rst", ".txt"))
                         or p.startswith(("docs/", "doc/"))]
            code_exts = (".py", ".js", ".ts", ".go", ".rs", ".rb", ".java", ".php")
            code_files = [p for p in paths if p.endswith(code_exts)]
            doc_file_ratio = round(len(doc_files) / len(code_files), 3) if code_files else 0.0

            missing = [doc for doc in _EXPECTED_DOCS
                       if not any(n == doc or n.upper().startswith(doc)
                                  or n.lower().startswith(doc.lower())
                                  for n in root_names)]
            return {
                "capability": self.name,
                "has_readme": has_readme,
                "doc_coverage": doc_coverage,
                "doc_coverage_scope": "python-public-docstrings",
                "doc_coverage_counts": {"documented": documented, "total": total},
                "doc_file_ratio": doc_file_ratio,
                "python_parse_errors": python_parse_errors,
                "missing_docs": missing,
            }
        finally:
            repo.cleanup()

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "DocumentationAnalysis"
    version = "1.0.0"
    description = "Measures documentation coverage (docstrings) and expected-document gaps"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000017: Configuration — من المحتوى، لا من أسماء فقط
# ---------------------------------------------------------------------------
_ENV_NAME = re.compile(
    r"(?i)(?:^|[-_.])(dev|development|test|testing|staging|prod|production|qa)(?:$|[-_.])")


class ConfigurationAnalysisCapability(ICapability):
    """Analyze configuration files — content-based, errors reported (R-W2-007)."""

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            from stack_detection import detect_config_files

            contents = repo.contents()
            paths = [p for p in contents if not p.startswith(".git/")]
            config_files = detect_config_files(paths, limit=50)

            # البيئات: من اسم الملف بكلمة كاملة (dev داخل «device» ليست بيئة)
            environments: List[str] = []
            for path in config_files:
                for part in os.path.basename(path).replace(".", "-").split("-"):
                    if _ENV_NAME.search(f"-{part}-"):
                        env = part.lower()
                        if env not in environments:
                            environments.append(env)

            # مشاكل حقيقية من المحتوى: JSON تالف، وملف أسرار مُودَع بلا مثال
            issues: List[Dict[str, Any]] = []
            checked = unreadable = 0
            for path in config_files:
                text = contents.get(path)
                if path.endswith(".json") and text is not None:
                    checked += 1
                    try:
                        json.loads(text)
                    except ValueError as exc:
                        issues.append({"file": path, "issue": f"invalid JSON: {exc}"[:150]})
                elif text is None:
                    unreadable += 1
            root_names = {os.path.basename(p) for p in paths if "/" not in p}
            # ``.env`` لا تصل اللقطة أصلاً (R-W2-005) — الفحص على القرص مباشرة
            # وحدة المدخل: مسار ``.env`` في الملفات أو على القرص — الدلالة وجودٌ لا تتبع git)
            env_present = any(p == ".env" for p in contents) or (
                repo.root and os.path.isfile(os.path.join(repo.root, ".env")))
            if env_present and ".env.example" not in root_names:
                issues.append({"file": ".env",
                               "issue": "secret file present with no .env.example template"})

            return {
                "capability": self.name,
                "config_files": config_files,
                "environments": environments,
                "issues": issues,
                "checked_json": checked,
                "unreadable": unreadable,   # محتوى لم يُقرأ ≠ «لا مشاكل»
            }
        finally:
            repo.cleanup()

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "ConfigurationAnalysis"
    version = "1.0.0"
    description = "Analyzes configuration files and their actual content"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000018: Infrastructure — أدلة من المحتوى، والاعتماد منفصل
# ---------------------------------------------------------------------------
_K8S_KIND = re.compile(r"(?m)^\s*kind:\s*(Deployment|Service|Pod|ReplicaSet|ConfigMap|"
                       r"Secret|Ingress|StatefulSet|DaemonSet|Job|CronJob)\s*$")
_K8S_API = re.compile(r"(?m)^\s*apiVersion:\s*[\w./]+\s*$")
_TF_PROVIDER = re.compile(r"(?m)^\s*provider\s+\"(aws|google|azurerm|azure)\"")
_CLOUD_SDKS = {"aws": ("boto3", "botocore"), "gcp": ("google-cloud-storage",),
               "azure": ("azure-storage-blob", "azure-identity")}


class InfrastructureAnalysisCapability(ICapability):
    """Analyze infrastructure footprint — evidence-based (R-W2-007).

    وجود SDK سحابي في الاعتماديات دليل اعتماد برمجي لا دليل بنية منشورة —
    لذلك يُفصل في cloud_evidence، ولا يُدّعى من الملفات صلاحية تشغيل.
    """

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            contents = repo.contents()
            docker: List[str] = []
            k8s: List[str] = []
            terraform: List[str] = []
            for path, text in sorted(contents.items()):
                base = os.path.basename(path)
                if base.startswith("Dockerfile") or base.startswith("docker-compose"):
                    docker.append(path)
                if path.endswith(".tf"):
                    terraform.append(path)
                if path.endswith((".yaml", ".yml")) and text and \
                        _K8S_API.search(text) and _K8S_KIND.search(text):
                    k8s.append(path)

            # السحابة: SDK من قائمة الاعتماديات الفعلية فقط (ليس مذكر في README؛ ليس اعتماداً)
            # + كتل provider في ملفات .tf فقط، بأسماء TF المطابقة للمزود
            from stack_detection import dependency_records, detect_stack
            dep_names = {str(rec.get("name")) for rec in
                        dependency_records(detect_stack(contents))}
            cloud_providers, cloud_evidence = [], {}
            _TF_NAMES = {"aws": ("aws",), "gcp": ("google",), "azure": ("azurerm",)}
            for provider, sdks in _CLOUD_SDKS.items():
                sdk_hits = [d for d in sorted(dep_names) if d in sdks]
                tf_hits = [path for path, text in sorted(contents.items())
                           if path.endswith(".tf") and text
                           and re.search(rf'provider\s+"({"|".join(_TF_NAMES[provider])})"',
                                         text)]
                if sdk_hits or tf_hits:
                    cloud_providers.append(provider)
                    cloud_evidence[provider] = {"sdk_dependencies": sdk_hits,
                                                "terraform_providers": tf_hits}

            return {
                "capability": self.name,
                "has_docker": bool(docker), "docker_evidence": docker,
                "has_kubernetes": bool(k8s), "kubernetes_evidence": k8s,
                "has_terraform": bool(terraform), "terraform_evidence": terraform,
                "cloud_providers": cloud_providers,
                "cloud_evidence": cloud_evidence,
                "cloud_evidence_type": "sdk-dependency-or-terraform-block",
            }
        finally:
            repo.cleanup()

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "InfrastructureAnalysis"
    version = "1.0.0"
    description = "Detects Docker/Kubernetes/Terraform evidence and cloud SDK dependencies"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000019: DNA — من stack_detection، وبصمة حقائق ثابتة الترتيب
# ---------------------------------------------------------------------------
class RepositoryDNAGenerationCapability(ICapability):
    """Generate a structured DNA fingerprint of a repository (R-W2-007).

    بصمة sha256 لحقائق مرتبة (لغات بأوزانها، أطر، مديرو حزم) — ثابتة مهما اختلف
    ترتيب الملفات؛ وهي بصمة حقائق لا بصمة محتوى، وهذا موثق في fingerprint_basis.
    """

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Dict[str, Any],
                             provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        الاكتساب المشترك — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (الاحتياط المعلن يبقى لمدخل execute العام وحده)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Dict[str, Any], provider: Any) -> Dict[str, Any]:
        repo = _acquire(input_data, provider)
        try:
            from stack_detection import (detect_package_managers, detect_stack,
                                        language_weights, primary_language)

            contents = repo.contents()
            report = detect_stack(contents)
            weights = language_weights(
                {p: c for p, c in contents.items() if c is not None})
            languages = sorted(weights, key=lambda lang: (-weights[lang].lines, lang))
            managers = detect_package_managers(list(contents), contents)

            facts = {
                "languages": [(lang, weights[lang].lines, weights[lang].files)
                              for lang in languages],
                "primary_language": primary_language(weights) if weights else "",
                "frameworks": sorted(report.frameworks),
                "package_managers": sorted(set(managers)),
            }
            digest = hashlib.sha256(
                json.dumps(facts, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()

            return {
                "capability": self.name,
                "languages": languages,
                "primary_language": primary_language(weights) if weights else "",
                "language_stats": {lang: {"lines": weights[lang].lines,
                                         "files": weights[lang].files}
                                  for lang in languages},
                "frameworks": list(report.frameworks),
                "package_managers": sorted(set(managers)),
                "fingerprint": digest,
                "fingerprint_basis": "sorted-facts-sha256",
            }
        finally:
            repo.cleanup()

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "RepositoryDNAGeneration"
    version = "1.0.0"
    description = "Generates the repository DNA from the kernel's stack detection"
    skills = ["CloneRepository", "WalkRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""



# ---------------------------------------------------------------------------
# CAPABILITY-000020: KnowledgeExtraction — من نتائج القدرات بالذات
# ---------------------------------------------------------------------------
class EngineeringKnowledgeExtractionCapability(ICapability):
    """Extract engineering knowledge from analysis results (R-W2-007).

    كل استنتاج موثّق بمصدره (القدرة والحقل)؛ وفحوص تعذرت تُمرَّر كفجوات —
    لا تتحول إلى اطمئنان. لا شيء يُخترع مما لم يُفحص.
    """

    def execute(self, input_data: Any) -> Dict[str, Any]:
        # عقد قديم: قائمة النتائج مباشرة؛ والجديد: قاموس يغلفها
        results = input_data
        if isinstance(input_data, dict):
            results = input_data.get("analysis_results")
        if not isinstance(results, list):
            raise ValueError("input needs analysis_results: a list of capability results")

        by_capability: Dict[str, Dict[str, Any]] = {}
        gaps: List[str] = []
        for i, res in enumerate(results):
            if not isinstance(res, dict) or "capability" not in res:
                gaps.append(f"result #{i}: no capability label — skipped")
                continue
            by_capability[res["capability"]] = res

        findings: List[Dict[str, str]] = []
        recommendations: List[Dict[str, str]] = []
        sec = by_capability.get("SecurityScan", {})
        if sec:
            if sec.get("secrets_found"):
                files = sorted({s["file"] for s in sec.get("secrets", [])})
                findings.append({"source": "SecurityScan.secrets_found",
                                  "finding": f"{sec['secrets_found']} potential secret(s)"})
                recommendations.append({"source": "SecurityScan",
                                          "recommendation": "rotate/remove committed secrets: "
                                          + ", ".join(files[:5])})
            if sec.get("vulnerabilities"):
                findings.append({"source": "SecurityScan.vulnerabilities",
                                 "finding": f"{len(sec['vulnerabilities'])} known-vulnerable "
                                           "pinned dependencies"})
                recommendations.append({"source": "SecurityScan",
                                        "recommendation": "upgrade the OSV-flagged pinned "
                                                          "dependencies"})
            if sec.get("osv_status") == "failed":
                gaps.append("SecurityScan: OSV check failed — vulnerability status unknown")
            elif sec.get("osv_status") == "partial":
                gaps.append("SecurityScan: OSV check partial — vulnerability status incomplete")
            elif sec.get("osv_status") == "skipped_no_pins":
                gaps.append("SecurityScan: no exact pins — OSV check not run")
            if sec.get("unresolved_dependencies"):
                gaps.append(f"SecurityScan: {len(sec['unresolved_dependencies'])} "
                           "range-constrained dependencies not vulnerability-checked")
            if sec.get("unreadable_files"):
                gaps.append(f"SecurityScan: {sec['unreadable_files']} files unreadable "
                           "— scan partial")
            if sec.get("manifest_parse_errors"):
                gaps.append(f"SecurityScan: manifest parse errors in "
                           f"{sec['manifest_parse_errors']}")
        else:
            gaps.append("SecurityScan result missing — security posture unknown")

        lic = by_capability.get("LicenseAnalysis", {})
        if lic:
            if lic.get("license") == "unknown":
                findings.append({"source": "LicenseAnalysis.license",
                                  "finding": "no recognizable license text"})
                recommendations.append({"source": "LicenseAnalysis",
                                        "recommendation": "add a standard LICENSE file (SPDX)"})
            if lic.get("mismatch"):
                findings.append({"source": "LicenseAnalysis.mismatch",
                                  "finding": f"declared {lic.get('declared_license')!r} but text "
                                             f"looks like {lic.get('license')!r}"})
            if lic.get("dependency_licenses_status") == "not_collected":
                gaps.append("LicenseAnalysis: dependency licenses not collected — "
                            "compatibility unknown")
        else:
            gaps.append("LicenseAnalysis result missing — license unknown")

        doc = by_capability.get("DocumentationAnalysis", {})
        if doc:
            if doc.get("missing_docs"):
                recommendations.append({"source": "DocumentationAnalysis",
                                        "recommendation": "add missing docs: "
                                                          + ", ".join(doc["missing_docs"])})
            counts = doc.get("doc_coverage_counts") or {}
            if counts.get("total"):
                findings.append({"source": "DocumentationAnalysis.doc_coverage",
                                 "finding": f"docstring coverage "
                                           f"{doc.get('doc_coverage', 0):.0%} "
                                           f"({counts.get('documented')}/{counts.get('total')})"})
        else:
            gaps.append("DocumentationAnalysis result missing — doc coverage unknown")

        dna = by_capability.get("RepositoryDNAGeneration", {})
        summary_parts: List[str] = []
        if dna:
            langs = dna.get("languages") or []
            primary = dna.get("primary_language") or (langs[0] if langs else None)
            if langs:
                summary_parts.append(
                    f"{len(langs)} language(s), primary {primary}")
            if dna.get("frameworks"):
                summary_parts.append(
                    f"frameworks: {', '.join(sorted(dna['frameworks'])[:5])}")
            if dna.get("package_managers"):
                summary_parts.append(
                    f"package managers: {', '.join(sorted(dna['package_managers']))}")
        if sec:
            summary_parts.append(f"security risk {sec.get('risk_level')}")

        return {
            "capability": self.name,
            "summary": "; ".join(summary_parts),
            "key_findings": findings,
            "recommendations": recommendations,
            "gaps": gaps,
        }

    # قيم معلنة كسمات صف — ليست دوال أصلاً (R-W2-007)
    name = "EngineeringKnowledgeExtraction"
    version = "1.0.0"
    description = "Derives grounded findings and recommendations from capability results"
    # "ReadRepository": نتائج التحليل التي يعمل عليها هذا الاستخراج مصدرها قراءة
    # المستودعات — والعقد يتطلب مهارة يساندها مزوّد مسجل.
    skills = ["ReadRepository"]
    def __init__(self):
        """القيم معلنة كسمات صف (R-W2-007)؛ الباني محفوظ للتوافق (G2 — لا حذف لرموز عام)."""

