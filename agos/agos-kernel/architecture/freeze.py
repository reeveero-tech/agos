"""AGOS Architecture Freeze v1.0.

فحص محتوى التجميد (إضافة لاحقة — سجل العمل 0084، ADR-0010): قدرة تحقق
مستقلة عن التصنيف النصي — خط أساس متعقب (ملف معتمد لا يُولد وقت التحقق)
يحمل النطاق ومنفستاً بصمة حتمية لأسماء الملفات ومحتواها؛ والتحقق يقارن
الشجرة الفعلية بالخط المسجل فيرصد التطابق/تغيير بايت/غياب ملف/ملفا
زائدا، وغياب خط الأساس عجز مسمى لا انهياراً ولا ادعاء امتثال. اعتماد
خط أساس فعلي لنطاق معتمد معلق على قرار الحوكمة (ADR-0010) — القدرة
مختبرة بالتثبيتات والحد معلن.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class FrozenComponent:
    """A frozen architectural component."""
    name: str
    version: str
    hash: str
    description: str
    frozen_at: datetime = field(default_factory=datetime.now)


@dataclass
class ArchitectureFreeze:
    """Architecture freeze declaration."""
    version: str = "1.0"
    frozen_at: datetime = field(default_factory=datetime.now)
    components: Dict[str, FrozenComponent] = field(default_factory=dict)
    allowed_changes: List[str] = field(default_factory=list)
    forbidden_changes: List[str] = field(default_factory=list)


# FROZEN COMPONENTS
FROZEN_COMPONENTS = {
    "kernel": FrozenComponent(
        name="Kernel",
        version="2.0.0",
        hash="frozen-kernel-v2",
        description="Core kernel responsibilities"
    ),
    "core_runtime": FrozenComponent(
        name="Core Runtime",
        version="2.0.0",
        hash="frozen-runtime-v2",
        description="Core execution runtime"
    ),
    "execution_contracts": FrozenComponent(
        name="Execution Contracts",
        version="2.0.0",
        hash="frozen-exec-contracts-v2",
        description="Mission, Capability, Provider contracts"
    ),
    "knowledge_ontology": FrozenComponent(
        name="Knowledge Ontology",
        version="1.0",
        hash="frozen-knowledge-ontology-v1",
        description="Knowledge graph schema"
    ),
    "policy_ontology": FrozenComponent(
        name="Policy Ontology",
        version="1.0",
        hash="frozen-policy-ontology-v1",
        description="Policy schema"
    ),
    "artifact_ontology": FrozenComponent(
        name="Artifact Ontology",
        version="1.0",
        hash="frozen-artifact-ontology-v1",
        description="Artifact schema"
    ),
    "public_apis": FrozenComponent(
        name="Public APIs",
        version="2.0.0",
        hash="frozen-apis-v2",
        description="Public API contracts"
    ),
    "sdk_contracts": FrozenComponent(
        name="SDK Contracts",
        version="2.0.0",
        hash="frozen-sdk-v2",
        description="SDK contracts"
    ),
    "event_model": FrozenComponent(
        name="Core Event Model",
        version="1.0",
        hash="frozen-events-v1",
        description="Core event schemas"
    ),
}

# ALLOWED AFTER FREEZE
ALLOWED_CHANGES = [
    "New Capabilities",
    "New Providers",
    "New Domains",
    "New Adapters",
    "New Knowledge Packs",
    "New Policies",
    "New Workflows",
    "New Templates",
    "New SDKs",
    "New Connectors",
    "Performance Improvements",
    "Security Improvements",
    "Reliability Improvements",
    "Bug Fixes",
]

# FORBIDDEN AFTER FREEZE
FORBIDDEN_CHANGES = [
    "Breaking Core Contracts",
    "Changing Kernel Responsibilities",
    "Moving Business Logic Into Core",
    "Creating Parallel Architectures",
    "Introducing Hidden State",
    "Violating Layer Boundaries",
]


# ---------------------------------------------------------------------------
# فحص محتوى التجميد (سجل العمل 0084 — ADR-0010): قدرة مستقلة عن التصنيف النصي
# ---------------------------------------------------------------------------

# موقع خط أساس محتوى التجميد المتعقب داخل المستودع (لا يُولد وقت التحقق)
FREEZE_CONTENT_BASELINE_DIR = "docs/architecture"
FREEZE_CONTENT_BASELINE_FILENAME = "freeze_content_baseline.json"


def _file_digest(path: Path) -> str:
    """بصمة محتوى الملف (sha256 سداسية) — حتمية للمحتوى نفسه."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_baseline_candidate_files(root: Path, rel: str) -> List[str]:
    """ملفات النطاق لمسار نسبي واحد — ترتيب حتمي (فرز المسارات).

    القاعدة الحتمية للشمول: كل الملفات تحت المسار (تكرارياً) عدا أدلة
    __pycache__ وملفات *.pyc (نواتج تنفيذ لا محتوى مصدر — استثناؤها في
    البناء والتحقق معاً فلا يظهر ملف زائد كاذب).
    المسار غير الموجود على الشجرة يُعاد فارغاً (صدق الغياب — يوثق لا يخفي).
    """
    target = root / rel
    if not target.exists():
        return []
    if target.is_file():
        return [rel]
    files: List[str] = []
    for p in target.rglob("*"):
        if p.is_dir():
            continue
        if any(part == "__pycache__" for part in p.parts):
            continue
        if p.suffix == ".pyc":
            continue
        files.append(p.relative_to(root).as_posix())
    return sorted(files)


def content_fingerprint(entries: Sequence[Tuple[str, str]]) -> str:
    """بصمة حتمية لمجموعة (مسار، بصمة محتوى) — على الفرز المرتب نفسه.

    بصمة الأسماء والمحتوى معاً: تغيير بايت يغير بصمة الملف فتغير البصمة
    الكلية، وملف زائد/ناقص يغير مجموعة الأسماء فتغيرها كذلك.
    """
    h = hashlib.sha256()
    for rel, digest in sorted(entries):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def build_freeze_content_baseline(
    root: Path, scope: Dict[str, List[str]]
) -> Dict[str, Any]:
    """بناء خط أساس لمحتوى نطاق التجميد — حتمي وقابل للتسلسل كما هو.

    الناتج قاموس خالص (بلا طوابع زمنية — الحتمية شرط البصمة): لكل مكوّن
    منفست مساراته وبصمات محتواها وأحجامها بالبايت، وبصمة كلية للمجموعة.
    خط الأساس المعتَمد يُلتزم كملف متعقب (docs/architecture/) ولا يُولد وقت
    التحقق — التوليد أداة إنشاء لا مسار تحقق.
    """
    components: Dict[str, Any] = {}
    all_entries: List[Tuple[str, str]] = []
    for component in sorted(scope):
        manifest: Dict[str, Any] = {}
        for rel in scope[component]:
            for rel_file in _iter_baseline_candidate_files(root, rel):
                digest = _file_digest(root / rel_file)
                manifest[rel_file] = {
                    "sha256": digest,
                    "bytes": (root / rel_file).stat().st_size,
                }
                all_entries.append((rel_file, digest))
        components[component] = {
            "scope": sorted(scope[component]),
            "files": manifest,
            "fingerprint": content_fingerprint(
                [(k, v["sha256"]) for k, v in sorted(manifest.items())]),
        }
    return {
        "format": "agos-freeze-content-baseline",
        "format_version": 1,
        "components": components,
        "fingerprint": content_fingerprint(all_entries),
    }


def verify_freeze_content(
    root: Path, baseline_path: Optional[Path] = None
) -> Dict[str, Any]:
    """التحقق من محتوى نطاق التجميد مقابل خط أساس متعقب — لا توليد وقت التحقق.

    العقد الصادق: النطاق يُقرأ من خط الأساس نفسه (لا يُشتق من الشجرة وقت
    التحقق فلا يتبدل النطاق بصمت)، والملفات تُقارن اسماً ومحتوى؛ وغياب خط
    الأساس عجز مسمى (verified=False بسبب مسمى) لا انهياراً ولا ادعاء
    امتثال مثبت. النتائج المسماة في findings: byte_change (تغيير بايت)،
    missing_file (ملف في الخط الأساس غائب عن الشجرة)، extra_file (ملف على
    الشجرة خارج الخط الأساس — بصمة الأسماء والمحتوى معاً)، وmatch للملفات
    المتطابقة. verified=True فقط بخط أساس موجود وصفر نتائج غير التطابق.
    """
    if baseline_path is None:
        baseline_path = (
            root / FREEZE_CONTENT_BASELINE_DIR / FREEZE_CONTENT_BASELINE_FILENAME)
    report: Dict[str, Any] = {
        "baseline_path": str(baseline_path),
        "verified": False,
        "reason": "",
        "files_checked": 0,
        "findings": [],
        "fingerprint": None,
    }
    if not baseline_path.exists():
        report["reason"] = (
            "غياب خط الأساس المتعقب — لا تحقق ممكن ولا ادعاء امتثال مثبت "
            f"(المسار المنتظر: {baseline_path})")
        return report
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report["reason"] = f"خط أساس غير قابل للقراءة: {type(exc).__name__}: {exc}"
        return report
    if not isinstance(baseline.get("components"), dict) or not baseline["components"]:
        report["reason"] = "خط الأساس بلا مكوّنات معتمدة — لا نطاق للتحقق"
        return report
    findings: List[Dict[str, Any]] = []
    files_checked = 0
    current_entries: List[Tuple[str, str]] = []
    for component, data in sorted(baseline["components"].items()):
        baseline_files: Dict[str, Any] = data.get("files", {})
        scope_paths: List[str] = data.get("scope", [])
        current_files: Dict[str, str] = {}
        for rel in scope_paths:
            for rel_file in _iter_baseline_candidate_files(root, rel):
                current_files[rel_file] = _file_digest(root / rel_file)
        for rel_file, digest in sorted(current_files.items()):
            current_entries.append((rel_file, digest))
        for rel_file in sorted(set(baseline_files) | set(current_files)):
            files_checked += 1
            in_baseline = rel_file in baseline_files
            on_disk = rel_file in current_files
            if in_baseline and on_disk:
                if baseline_files[rel_file]["sha256"] == current_files[rel_file]:
                    findings.append({
                        "component": component, "kind": "match",
                        "path": rel_file, "detail": ""})
                else:
                    findings.append({
                        "component": component, "kind": "byte_change",
                        "path": rel_file,
                        "detail": "بصمة المحتوى تغيرت عن خط الأساس"})
            elif in_baseline and not on_disk:
                findings.append({
                    "component": component, "kind": "missing_file",
                    "path": rel_file,
                    "detail": "في خط الأساس وغائب عن الشجرة"})
            else:
                findings.append({
                    "component": component, "kind": "extra_file",
                    "path": rel_file,
                    "detail": "على الشجرة وخارج خط الأساس (بصمة الأسماء)"})
    non_match = [f for f in findings if f["kind"] != "match"]
    report["files_checked"] = files_checked
    report["findings"] = findings
    report["fingerprint"] = content_fingerprint(current_entries)
    if non_match:
        report["reason"] = (
            f"{len(non_match)} نتيجة غير تطابق (تغيير بايت/غياب ملف/ملف زائد) — "
            "المحتوى لا يطابق خط الأساس")
    else:
        report["verified"] = True
        report["reason"] = "تطابق كامل مع خط الأساس المتعقب (أسماء ومحتوى)"
    return report


class ArchitectureFreezeManager:
    """Manages architecture freeze."""
    
    def __init__(self):
        self.freeze = ArchitectureFreeze(
            version="1.0",
            components=FROZEN_COMPONENTS,
            allowed_changes=ALLOWED_CHANGES,
            forbidden_changes=FORBIDDEN_CHANGES,
        )
        # حكم المقيم المشترك الأخير وسببه — متاح لنقل سبب المنع
        self.last_verdict = None
    
    def get_component(self, name: str) -> FrozenComponent:
        """Get a frozen component."""
        return self.freeze.components.get(name)
    
    def is_frozen(self, component: str) -> bool:
        """Check if component is frozen."""
        return component in self.freeze.components
    
    def is_allowed(self, change: str) -> bool:
        """Check if change is allowed — عضوية كاملة بعد توحيد الحالة."""
        normalized = str(change).strip().casefold()
        return normalized in {
            str(c).strip().casefold()
            for c in self.freeze.allowed_changes}
    
    def is_forbidden(self, change: str) -> bool:
        """Check if change is forbidden — أصلحت الخاصية المعطوبة (كانت
        تقرأ self.frozen_changes غير الموجودة فترمي AttributeError دائماً)."""
        normalized = str(change).strip().casefold()
        return normalized in {
            str(c).strip().casefold()
            for c in self.freeze.forbidden_changes}
    
    def validate_change(self, change: str, component: str) -> tuple[bool, str]:
        """Validate if a change is allowed — الحكم النهائي عبر المقيم
        المشترك (R-W1-007 — الشريحة السادسة، ADR-0010): مواصفة العضوية تُبنى
        من الإعلان الحالي نفسه عند كل حكم فلا تنفصل قوائم المدير عن قوائم
        حكم المقيم، والحكم يتبع الإعلان إن تغيّر. المثبت محدود: التصنيف
        النصي المقدم مسموح/ممنوع وفق إعلان التجميد — لا حكماً على التغيير
        البرمجي الفعلي. لا سماح أعمى بالسقوط (كان التصنيف المجاهل على
        مكوّن مجمد وأي تغيير على مكوّن غير مجمد يرجعان True دائماً)."""
        from agos_kernel.governance.policy_evaluator import (
            VERDICT_COMPLIANT, FREEZE_CHANGE_RULE_ID, freeze_change_spec,
            get_shared_evaluator)
        evaluator = get_shared_evaluator()
        # المواصفة من الإعلان الحالي نفسه — مرجعية واحدة للحكم والقراءة
        evaluator.register_spec(
            FREEZE_CHANGE_RULE_ID,
            freeze_change_spec(
                list(self.freeze.components),
                self.freeze.allowed_changes,
                self.freeze.forbidden_changes))
        self.last_verdict = evaluator.evaluate(
            FREEZE_CHANGE_RULE_ID,
            {"type": "ArchitectureChange",
             "change": change, "component": component})
        # السبب المُعاد يوضح حدود المثبت — لا عبارة سماح مطلقة
        return (self.last_verdict.verdict == VERDICT_COMPLIANT,
                self.last_verdict.reason)

    def verify_content(
        self, root: Path, baseline_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """واجهة المدير لفحص محتوى التجميد — تفويض للقدرة المستقلة
        (verify_freeze_content — سجل العمل 0084): خط أساس متعقب لا يُولد وقت
        التحقق، وبصمة حتمية للأسماء والمحتوى، وغياب الخط عجز مسمى لا
        ادعاء امتثال مثبت."""
        return verify_freeze_content(root, baseline_path)
    
    def get_frozen_components(self) -> List[FrozenComponent]:
        """Get all frozen components."""
        return list(self.freeze.components.values())
    
    def get_summary(self) -> Dict[str, Any]:
        """Get freeze summary."""
        return {
            "version": self.freeze.version,
            "frozen_at": self.freeze.frozen_at.isoformat(),
            "components_count": len(self.freeze.components),
            "allowed_changes_count": len(self.freeze.allowed_changes),
            "forbidden_changes_count": len(self.freeze.forbidden_changes),
            "components": [c.name for c in self.freeze.components.values()],
        }


# Global freeze manager
_freeze_manager = ArchitectureFreezeManager()


def get_freeze_manager() -> ArchitectureFreezeManager:
    return _freeze_manager


# Test
def test_architecture_freeze():
    """Test architecture freeze."""
    print("=" * 60)
    print("AGOS ARCHITECTURE FREEZE v1.0")
    print("=" * 60)
    
    manager = get_freeze_manager()
    summary = manager.get_summary()
    
    print(f"\nVersion: {summary['version']}")
    print(f"Frozen At: {summary['frozen_at']}")
    
    print(f"\nFrozen Components ({summary['components_count']}):")
    for component in summary['components']:
        print(f"  - {component}")
    
    print(f"\nAllowed Changes ({summary['allowed_changes_count']}):")
    for change in ALLOWED_CHANGES[:5]:
        print(f"  + {change}")
    print(f"  ... and {len(ALLOWED_CHANGES) - 5} more")
    
    print(f"\nForbidden Changes ({summary['forbidden_changes_count']}):")
    for change in FORBIDDEN_CHANGES:
        print(f"  ✗ {change}")
    
    print("\nValidation Tests:")
    valid, msg = manager.validate_change("New Capabilities", "kernel")
    print(f"  New Capabilities on kernel: {msg}")
    
    valid, msg = manager.validate_change("Breaking Core Contracts", "kernel")
    print(f"  Breaking Core Contracts on kernel: {msg}")
    
    print("\n" + "=" * 60)
    print("ARCHITECTURE FREEZE DECLARED")
    print("=" * 60)
    
    return manager


if __name__ == "__main__":
    test_architecture_freeze()