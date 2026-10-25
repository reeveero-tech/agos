"""R-W2-013 — RPP: خط معالجة المستودعات وفق وثيقته (Repository Processing Pipeline).

المراحل الثماني الموثقة (``agos/rpp-pipeline/README.md``) فوق الخط الموحد
(ADR-0005 — ``capabilities/analysis_service``): لا مسح جديد ولا قراءة قرص
إضافية — كل قرار من مصدره الواحد (``stack_detection`` للغات/الأطر/الاعتماديات/
نقاط الدخول/الإعدادات)، والكواشف إسقاطات حاملة للأدلة فوق الحقائق.

مصفوفة المطابقة (المرحلة ← القائم المُعاد استخدامه ← الإضافة):
- **M1 الموحّد**: إسقاط URO فوق ``SharedAnalysis`` — القرارات من
  ``stack_detection`` (المصدر الواحد نفسه الذي يفوّض إليه كاشفو rie؛ رie
  يُسقط نتائج بلا أدلة ولا ثقة فبقي هو واجهة rie، وRPP إسقاطه الحامل
  للأدلة — لا قاعدة قرار ثانية).
- **M2 سوق الكواشف**: ``DetectorPlugin`` بالواجهة الموثقة حرفياً
  (name/version/category/detect(uro)/confidence(feature)) — سجل داخل
  العملية؛ التثبيت/التحديث/الإزالة الخارجية (CLI) متطلب موثق مؤجل
  (يحتاج آلية توزيع حزم) — البند PARTIAL والمتبقي في سجل العمل.
- **M3 استخراج السمات**: ``FeatureSet`` بأدلة مسماة وثقة — الدمج حتمي
  غير معتمد على ترتيب التسجيل، والمتعارض يوثَّق بمصادره كلها.
- **M4 الرسم المعرفي**: رسم سمات (REPOSITORY-USES-FEATURE) في الذاكرة —
  منفصل عن رسم الحضارة (عقد مستودع/اعتمادية بدلالة مختلفة) والسبب موثق،
  والحالة الفعّالة تُحدَّث (الحواف الزائلة تُزال) والتاريخ في الأحداث.
- **M5 التشابه**: Jaccard للمفاتيح + cosine حقيقي فوق متجهات ثنائية
  للعناصر (مفتاح، قيمة) — مع تصحيح موثق لمثال الوثيقة (صدق القيم هناك
  يساوي "Python" و"Go")، والقيم الفارغة ليست سمات فعلية.
- **M6 التطور**: NEW/REMOVED/CHANGED بين نسختين (التزامين) بمفتاح هوية
  كاملة، وآخر نسخة لكل (مصدر، فرع) — إعادة النسخة نفسها لا تنتج أحداثاً.
- **M7 الثقة**: أوزان الوثيقة (درجات استدلالية موثقة لا احتمالات مقيسة) —
  مصدر واحد، والدرجة تُحسب دائماً من الأدلة المنشورة نفسها بعد الدمج،
  والحواف تحمل ثقة سماتها.
- **M8 طابور القياس**: الأهلية الثلاثية بالقيم لا بالمفاتيح (قدرات مكتشفة
  + تعريف CI + إطار اختبار مصرّح)، والنجوم مدخل موثق اختياري (المجهول ليس
  صفراً)، وفقدان الأهلية يُحدّث الطابور لا يتركه يكذب، والتسليم إلى ARI
  متطلب موثق مؤجل (لا منفذ تشغيلي — R-W2-011 محجوب) معلن لا مُدّعى.

مبدأ الأمانة (ADR-0002): الإشارات لا تُرفع — وجود Dockerfile «تعريف حاوية»
لا بناء ناجح، والاعتمادية المصرّح بها «تصريح» لا تنفيذ، ووجود workflow
«تعريف CI» لا اختبارات تعمل. والغياب غير المحسوم يبقى مجهولاً لا False.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from interfaces import ICapability

__all__ = [
    "UniversalRepositoryObject", "Feature", "FeatureSet", "DetectorPlugin",
    "RPPDetectorRegistry", "RPPKnowledgeGraph", "SimilarityEngine",
    "EvolutionTracker", "ConfidenceEngine", "BenchmarkQueue",
    "RPPKnowledgeBase", "RPPPipeline", "RepositoryProcessingPipelineCapability",
]

RPP_SCHEMA_VERSION = "rpp-1.0"
RPP_RULES_VERSION = "rpp-stages-1"

#: مفتاح المستودع للرسم والطابور: (المصدر، الفرع) — الحالة الفعالة
#: لمستودع واحد مهما تعددت نسخه المعالجة (النسخة تتمايز في التطور).
def repo_key(identity: Tuple[str, str, str]) -> Tuple[str, str]:
    return (identity[0], identity[1])

# ---------------------------------------------------------------------------
# M7 — محرك الثقة: المصدر الواحد لأوزان الأدلة (درجات استدلالية موثقة، لا
# احتمالات مقيسة — الوثيقة نفسها تسميها استدلالية)
# ---------------------------------------------------------------------------

EVIDENCE_WEIGHTS: Dict[str, float] = {
    "import": 1.0,
    "config": 0.95,
    "file": 0.90,
    "documentation": 0.80,
    "code": 0.85,
    "inference": 0.50,
}


class ConfidenceEngine:
    """M7 — ثقة السمة من نوع أدلتها (جدول الوثيقة نفسه، مصدر واحد).

    الدرجة تُحسب دائماً من الأدلة المنشورة نفسها (بعد أي دمج) — فالسمة
    وحافتها في الرسم يحملان الدرجة ذاتها التي يعطيها المحرك لأدلتها.
    """

    version = "confidence-1.0"

    def calculate(self, evidence: List[str]) -> float:
        """الناتج: جداء أوزان أنواع الأدلة — والتعزيز/العقوبة بعدّادها.

        ``evidence`` إدخالات ``"type:detail"`` — النوع من جدول الوثيقة، وما
        عداه وزن 0.5 (غير معروف). لا ادعاء قياس: الدرجة استدلالية موثقة،
        وسقفها 1.0 (أدلة وزن 1 لا ترتفع فوق اليقين — والتعزيز يظهر حيث
        الأوزان أقل من 1).
        """
        confidence = 1.0
        for ev in evidence:
            kind = ev.split(":", 1)[0] if ":" in ev else ev
            confidence *= EVIDENCE_WEIGHTS.get(kind, 0.5)
        if len(evidence) > 3:
            confidence *= 1.1
        elif len(evidence) == 0:
            confidence *= 0.1
        return min(confidence, 1.0)

    def filter_by_confidence(self, features: "FeatureSet",
                             threshold: float = 0.6) -> "FeatureSet":
        """نسخة بسمات فوق العتبة — الأصل لا يُعدل (G2: تحسين لا حذف)."""
        kept = {k: v for k, v in features.features.items()
                if v.confidence >= threshold}
        return FeatureSet(repository=features.repository,
                         features=dict(kept),
                         detected_at=features.detected_at,
                         detectors_used=list(features.detectors_used),
                         gaps=list(features.gaps))


# المثيل المشترك — مصدر واحد للكواشف والدمج والحواف
_CONFIDENCE = ConfidenceEngine()


# ---------------------------------------------------------------------------
# M1 — الموحّد: URO إسقاط صرف فوق حقائق الخط الموحد
# ---------------------------------------------------------------------------

@dataclass
class UniversalRepositoryObject:
    """الشكل الموحد لأي مستودع — من الحقائق المشتركة فقط.

    ``github_data`` ‏None دائماً في هذا السياق (لا شبكة ولا اختراع) — والفجوة
    مسماة. ``configs`` يحمل نتائج التحليل الفعلية وأخطاءها لا قائمة أسماء
    ولا صدق وجود نص.
    """
    # الهوية — المستودع والنسخة (الاسم وحده لا يكفي)
    url: str = ""
    name: str = ""
    owner: str = ""
    branch: str = ""
    commit: str = ""
    path: str = ""

    # الفهرس
    files: List[Dict[str, Any]] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)

    # القرارات — من المصدر الواحد (stack_detection)
    primary_language: str = ""
    all_languages: List[str] = field(default_factory=list)
    language_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    framework_evidence: List[Dict[str, Any]] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    entry_points: List[Any] = field(default_factory=list)

    # نتائج التحليل الفعلية وأخطاؤها (لا مجرد أسماء ولا صدق وجود نص)
    configs: Dict[str, Any] = field(default_factory=dict)
    manifest_errors: Dict[str, str] = field(default_factory=dict)

    # إشارات القدرات الإنتاجية من جينوم القدرات (R-W2-012) — استخدام فعلي
    # موثق بالأدلة في كود الإنتاج، لا تصريح اعتمادية
    capability_usage: Dict[str, Any] = field(default_factory=dict)

    # النقص المسمّى من الحقائق نفسها
    unread: Dict[str, str] = field(default_factory=dict)
    scan_errors: Dict[str, str] = field(default_factory=dict)

    github_data: Optional[Dict[str, Any]] = None

    normalized_at: str = ""
    version: str = RPP_SCHEMA_VERSION
    input_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url, "name": self.name, "owner": self.owner,
            "branch": self.branch, "commit": self.commit, "path": self.path,
            "files": self.files, "directories": self.directories,
            "primary_language": self.primary_language,
            "all_languages": self.all_languages,
            "language_stats": self.language_stats,
            "dependencies": self.dependencies, "frameworks": self.frameworks,
            "framework_evidence": self.framework_evidence,
            "config_files": self.config_files, "entry_points": self.entry_points,
            "configs": self.configs, "manifest_errors": self.manifest_errors,
            "capability_usage": self.capability_usage,
            "unread": self.unread, "scan_errors": self.scan_errors,
            "github_data": self.github_data,
            "normalized_at": self.normalized_at, "version": self.version,
            "input_fingerprint": self.input_fingerprint,
        }

    @property
    def identity(self) -> Tuple[str, str, str]:
        """هوية النسخة: (المصدر، الفرع، الالتزام) — والمستودع المحلي بلا
        التزام تُميّز نسخته ببصمة مدخلاته (فلا تُستبدل نسخ محلّلة مختلفة).
        """
        source = self.url or self.path
        version = self.commit or f"fp:{self.input_fingerprint}"
        return (source, self.branch, version)


def _fingerprint(files: List[Dict[str, Any]]) -> str:
    """بصمة حتمية للمدخلات المحللة فعلاً — المسار وهضم المحتوى.

    الهضم من المحتوى المقروء في الحقائق المشتركة (هاش كامل للمقروء، وهاش
    المسح المخزن لغيره)، وما لم يُقرأ فالحجم والأسطر — لكل ملف طبقة تثبت
    حالته، والغياب يبقى غياباً لا اختراعاً.
    """
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x.get("path", "")):
        h.update(str(f.get("path", "")).encode())
        if f.get("digest"):
            h.update(str(f["digest"]).encode())
        else:
            h.update(str(f.get("size", 0)).encode())
            h.update(str(f.get("lines", -1)).encode())
    return "sha256:" + h.hexdigest()


def _capability_usage(shared: Any) -> Dict[str, Any]:
    """إشارات القدرات الإنتاجية من جينوم القدرات (R-W2-012) — إسقاط صرف.

    المهارة المدعومة ساكنياً = استخدام فعلي موثق بالدليل في كود الإنتاج
    (ملف/سطر/رمز) — والقدرة المؤلفة المتحققة تركيب ساكن موثق. لا تصريح
    اعتمادية ولا ادعاء تحقق تشغيلي — والمرجع موثق بأدلته في الأصل.
    """
    from capabilities.genome import build_capability_genome
    genome = build_capability_genome(
        shared, generated_at=datetime.now(timezone.utc))
    skills: Dict[str, Any] = {}
    for name, skill in genome.get("skills", {}).items():
        if skill.get("status") == "statically_supported":
            # دليل الإنتاج فقط — نتائج الاختبار لا تثبت قدرة إنتاجية
            skills[name] = [
                {"file": f.get("file"), "line": f.get("line"),
                 "symbol": f.get("symbol"), "context": f.get("context")}
                for f in skill.get("findings", [])
                if f.get("context") == "production"]
    capabilities = sorted(
        name for name, cap in genome.get("capabilities", {}).items()
        if cap.get("status") == "verified")
    return {"statically_supported_skills": skills,
            "verified_capabilities": capabilities,
            "catalog_skill_count": genome.get("catalog_skill_count", 0),
            # فجوات التحليل المؤثرة في قرار القدرات تُنقل لا تُسقط
            "gaps": list(genome.get("gaps", []))}


def _manifest_analysis(manifests: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """نتائج تحليل الملفات البيانية الفعلية وأخطاؤها — لا صدق وجود نص.

    الملف غير الفارغ الفاسد يُسجَّل خطأً مسمّى لا نجاحاً، ونتيجة التحليل
    عدد الاعتماديات المحلولة فعلاً من المصدر الواحد (parse_manifest).
    """
    from stack_detection import parse_manifest
    results: Dict[str, Any] = {}
    for path, content in sorted(manifests.items()):
        if content is None:
            results[path] = {"analyzed": False, "error": "unread-content"}
            continue
        try:
            deps = parse_manifest(path, content)
        except Exception as exc:  # noqa: BLE001 — خطأ تحليل مسمّى لا فشل صامت
            results[path] = {"analyzed": False,
                             "error": f"{type(exc).__name__}: {exc}"}
        else:
            results[path] = {"analyzed": True,
                             "dependencies": len(deps)}
    return results


class UniversalNormalizer:
    """M1 — التطبيع: URO من ``SharedAnalysis`` (إسقاط، لا مسح)."""

    version = "normalizer-1.0"

    def normalize(self, shared: Any, *, normalized_at: datetime) -> UniversalRepositoryObject:
        from stack_detection import (dependency_records, detect_config_files,
                                     detect_entry_points, detect_stack,
                                     is_manifest, language_weights)

        non_dir = [f for f in shared.files if not f.is_dir]
        # الهضم فوق المحتوى المقروء فعلاً (حقائق الخط الموحد) — إسقاط لا مسح
        index = [{"path": f.path, "size": f.size_bytes, "extension": f.extension,
                  "lines": f.lines,
                  "digest": (hashlib.sha256(shared.contents[f.path].encode())
                             .hexdigest() if shared.contents.get(f.path) is not None
                             else f.sha256)}
                 for f in non_dir]
        dirs = sorted(f.path for f in shared.files if f.is_dir)
        manifests = {p: shared.contents.get(p) for p in
                     [f.path for f in non_dir] if is_manifest(p)}
        stack = shared.stack or detect_stack(manifests)
        # اللغات وإحصاءاتها من حقائق الخط الموحد نفسها (الفهرس الكامل —
        # لا المحتوى المقروء وحده) — R-W2-003: الترتيب بالأسطر ثم الملفات
        weights = shared.code_languages or language_weights(
            {f.path: shared.contents.get(f.path) for f in non_dir})
        ordered = sorted(weights.values(), key=lambda s: (-s.lines, -s.files))
        langs = [stat.language for stat in ordered]
        stats = {stat.language: {"files": stat.files, "lines": stat.lines}
                 for stat in ordered}

        uro = UniversalRepositoryObject(
            url=shared.meta.get("url", "") or shared.source_url,
            name=shared.meta.get("name", ""),
            owner=shared.meta.get("owner", ""),
            branch=shared.source_branch, commit=shared.source_commit,
            path=shared.source_path,
            files=index, directories=dirs,
            primary_language=langs[0] if langs else "",
            all_languages=langs,
            language_stats=stats,
            dependencies=[dict(r) for r in dependency_records(stack)],
            frameworks=list(stack.frameworks),
            framework_evidence=[e.to_dict() for e in stack.evidence],
            config_files=sorted(detect_config_files([f.path for f in non_dir])),
            entry_points=detect_entry_points(
                [f.path for f in non_dir], manifests),
            capability_usage=_capability_usage(shared),
            configs={"manifests_analyzed": sorted(manifests),
                     "manifest_results": _manifest_analysis(manifests)},
            manifest_errors={p: r["error"] for p, r in
                            _manifest_analysis(manifests).items()
                            if not r.get("analyzed")},
            unread=dict(shared.unread),
            scan_errors=dict(shared.scan_errors),
            github_data=None,
            normalized_at=normalized_at.isoformat(),
            input_fingerprint=_fingerprint(index),
        )
        return uro


# ---------------------------------------------------------------------------
# M2 — سوق الكواشف: واجهة الوثيقة حرفياً (detect/confidence) بأدلة مسماة
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    """سمة واحدة بأدلة مسماة — القيمة لا تدّعي أكثر مما يثبته الدليل.

    ``conflicts`` توثق الادعاءات المتعارضة بنيتهاً (المصدر/القيمة/الأدلة
    لكل ادعاء) — فالقيمة المتنازع عليها ليست حقيقة مؤسسة ولا تُستخدم في
    الأهلية، والترجيح المعلن للقيمة المعتمدة قاعدة استقرار موثقة (المصدر
    الأصغر معجمياً) لا ادعاء صحة.
    """
    name: str
    value: Any
    confidence: float = 0.0
    source: str = ""
    evidence: List[str] = field(default_factory=list)
    detected_at: str = ""
    conflicts: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_contested(self) -> bool:
        """قيمة متنازع عليها — ليست حقيقة مؤسسة فلا تمنح أهلية."""
        return bool(self.conflicts)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value,
                "confidence": round(self.confidence, 4), "source": self.source,
                "evidence": self.evidence, "detected_at": self.detected_at,
                "conflicts": self.conflicts}


@dataclass
class FeatureSet:
    """سمات مستودع واحد — بأدلة وفجوات مسماة."""
    repository: Tuple[str, str, str]   # (source, branch, commit)
    features: Dict[str, Feature] = field(default_factory=dict)
    detected_at: str = ""
    detectors_used: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"repository": list(self.repository),
                "features": {k: v.to_dict() for k, v in self.features.items()},
                "detected_at": self.detected_at,
                "detectors_used": self.detectors_used,
                "gaps": self.gaps}


class DetectorPlugin(ABC):
    """واجهة الوثيقة حرفياً — القرار من المصدر الواحد والدليل مسمّى.

    ``detect(uro)`` يستخرج السمات بأدلتها، و``confidence(feature)`` يحسب
    ثقتها من أدلتها المنشورة (تفويض إلى المحرك الموحد — مصدر واحد).
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def category(self) -> str: ...

    @abstractmethod
    def detect(self, uro: UniversalRepositoryObject) -> List[Feature]: ...

    @abstractmethod
    def confidence(self, feature: Feature) -> float: ...

    def _finalize(self, feature: Feature) -> Feature:
        """الثقة من الأدلة المنشورة نفسها — عبر الواجهة الموثقة."""
        feature.confidence = self.confidence(feature)
        return feature


class _LanguagePlugin(DetectorPlugin):
    name, version, category = "LanguageDetector", "1.0.0", "language"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        if not uro.all_languages:
            return []
        stat = uro.language_stats
        feature = Feature(
            name="languages", value=list(uro.all_languages),
            source=self.name,
            evidence=[f"file:{l}:{stat[l]['lines']} lines"
                      for l in uro.all_languages])
        return [self._finalize(feature)]


class _FrameworkPlugin(DetectorPlugin):
    name, version, category = "FrameworkDetector", "1.0.0", "framework"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        if not uro.frameworks:
            return []
        ev = [f"config:manifest:{e.get('manifest', '')}"
              for e in uro.framework_evidence]
        return [self._finalize(Feature(
            name="frameworks", value=list(uro.frameworks),
            source=self.name, evidence=ev))]


class _DependencyPlugin(DetectorPlugin):
    name, version, category = "DependencyDetector", "1.0.0", "dependency"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        if not uro.dependencies:
            return []
        return [self._finalize(Feature(
            name="dependencies",
            value=[d.get("name") for d in uro.dependencies],
            source=self.name,
            evidence=[f"config:{d.get('name')}@{d.get('ecosystem')}"
                      for d in uro.dependencies]))]


class _EntryPointPlugin(DetectorPlugin):
    """نقاط دخول قابلة للتنفيذ — قدرة موثقة (أوامر يوفرها المستودع)."""
    name, version, category = "EntryPointDetector", "1.0.0", "capability"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        if not uro.entry_points:
            return []
        return [self._finalize(Feature(
            name="entry_points", value=list(uro.entry_points),
            source=self.name,
            evidence=[f"file:{p}" if ":" not in str(p) else f"config:{p}"
                      for p in uro.entry_points]))]


class _ContainerDefinitionPlugin(DetectorPlugin):
    """وجود Dockerfile يثبت تعريف حاوية — لا نجاح بناء (لا رفع إشارة)."""
    name, version, category = "ContainerDefinitionDetector", "1.0.0", "infrastructure"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        dockerfiles = [f["path"] for f in uro.files
                       if f["path"].rsplit("/", 1)[-1] == "Dockerfile"]
        if not dockerfiles:
            return []
        return [self._finalize(Feature(
            name="container_definition_present", value=sorted(dockerfiles),
            source=self.name,
            evidence=[f"file:{p}" for p in sorted(dockerfiles)]))]


class _CIWorkflowPlugin(DetectorPlugin):
    """وجود workflow يثبت تعريف CI — لا أن الاختبارات تعمل."""
    name, version, category = "CIWorkflowDetector", "1.0.0", "quality"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        workflows = [f["path"] for f in uro.files
                     if f["path"].replace("\\", "/").startswith(".github/workflows/")]
        if not workflows:
            return []
        return [self._finalize(Feature(
            name="ci_workflow_definitions_present", value=sorted(workflows),
            source=self.name,
            evidence=[f"file:{p}" for p in sorted(workflows)]))]


class _TestingDeclaredPlugin(DetectorPlugin):
    """اعتمادية إطار اختبار مصرّح بها — تصريح لا تشغيل اختبارات."""
    name, version, category = "TestingDeclaredDetector", "1.0.0", "quality"
    _TEST_DEPS = {"pytest", "tox", "nox", "jest", "vitest", "mocha",
                  "go-test", "cargo-test"}

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        declared = sorted({d.get("name") for d in uro.dependencies
                           if d.get("name") in self._TEST_DEPS})
        if not declared:
            return []
        eco = {d.get("name"): d.get("ecosystem") for d in uro.dependencies}
        return [self._finalize(Feature(
            name="testing_frameworks_declared", value=declared,
            source=self.name,
            evidence=[f"config:{d}@{eco.get(d)}" for d in declared]))]


class _AIDeclaredPlugin(DetectorPlugin):
    """اعتماديات AI مصرّح بها — تصريح لا قدرة منفذة."""
    name, version, category = "AIDeclaredDetector", "1.0.0", "ai"
    _AI_DEPS = {"langchain", "llama-index", "llamaindex", "litellm", "openai",
                "anthropic", "transformers", "torch", "tensorflow"}

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        declared = sorted({d.get("name") for d in uro.dependencies
                           if d.get("name") in self._AI_DEPS})
        if not declared:
            return []
        return [self._finalize(Feature(
            name="ai_libraries_declared", value=declared,
            source=self.name,
            evidence=[f"config:{d}" for d in declared]))]


class _ProductionCapabilityPlugin(DetectorPlugin):
    """استخدام فعلي للقدرات في كود الإنتاج — من جينوم القدرات (R-W2-012).

    المهارة المدعومة ساكنياً لها دليل ملموس (ملف/سطر/رمز) — إشارة ساكنة
    موثقة لا ادعاء تحقق تشغيلي. هذا هو شرط «القدرات» في أهلية القياس:
    إشارة مصدرها الموثق القائم (CGP)، لا أسماء أطر ولا تصريحات.
    """
    name, version, category = "ProductionCapabilityDetector", "1.0.0", "capability"

    def confidence(self, feature):
        return _CONFIDENCE.calculate(feature.evidence)

    def detect(self, uro):
        usage = uro.capability_usage or {}
        skills = usage.get("statically_supported_skills") or {}
        verified = usage.get("verified_capabilities") or []
        if not skills and not verified:
            return []
        evidence = [
            f"code:{name}:{f['file']}:{f['line']}"
            for name, findings in sorted(skills.items())
            for f in findings[:3]]
        evidence += [f"code:capability:{c}" for c in verified]
        value = sorted(skills) + sorted(verified)
        return [self._finalize(Feature(
            name="production_capability_usage", value=value,
            source=self.name, evidence=evidence))]


class RPPDetectorRegistry:
    """M2 — سجل الكواشف داخل العملية (تثبيت/تحديث خارجيان: مؤجلان موثقان)."""

    def __init__(self):
        self._plugins: Dict[str, DetectorPlugin] = {}

    def register(self, plugin: DetectorPlugin) -> None:
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Optional[DetectorPlugin]:
        return self._plugins.get(name)

    def list_all(self) -> List[DetectorPlugin]:
        return list(self._plugins.values())

    def detect_all(self, uro: UniversalRepositoryObject
                   ) -> Tuple[List[Tuple[DetectorPlugin, Feature]], List[str]]:
        """تشغيل الجميع — فشل أي واجهة من واجهتي الكاشف فجوة مسماة لا
        فشل صامت للخط كله (الكواشف الأخرى تستمر).

        يُعاد (الكاشف، السمة) معاً — فالثقة تُطلب من كاشفها بالواجهة
        الموثقة ``confidence(feature)`` داخل حدود الحماية نفسها.
        """
        pairs: List[Tuple[DetectorPlugin, Feature]] = []
        failures: List[str] = []
        for plugin in sorted(self._plugins.values(), key=lambda p: p.name):
            try:
                for feature in plugin.detect(uro):
                    feature.confidence = plugin.confidence(feature)
                    pairs.append((plugin, feature))
            except Exception as exc:  # noqa: BLE001 — فجوة مسماة
                failures.append(f"{plugin.name}: {type(exc).__name__}: {exc}")
        return pairs, failures


def create_default_registry() -> RPPDetectorRegistry:
    registry = RPPDetectorRegistry()
    for plugin in (_LanguagePlugin(), _FrameworkPlugin(), _DependencyPlugin(),
                  _EntryPointPlugin(), _ContainerDefinitionPlugin(),
                  _CIWorkflowPlugin(), _TestingDeclaredPlugin(),
                  _AIDeclaredPlugin(), _ProductionCapabilityPlugin()):
        registry.register(plugin)
    return registry


# ---------------------------------------------------------------------------
# M3 — استخراج السمات: دمج حتمي (لا يعتمد على ترتيب التسجيل)
# ---------------------------------------------------------------------------

def extract_features(uro: UniversalRepositoryObject,
                     registry: RPPDetectorRegistry,
                     *, detected_at: str) -> FeatureSet:
    pairs, failures = registry.detect_all(uro)

    # تجميع الادعاءات بالاسم — والدمج حتمي: القيمة المعتمدة من المصدر
    # الأصغر معجمياً (قاعدة استقرار معلنة لا ادعاء صحة)، والتعارض — إن
    # وُجد — يوثَّق بنيةً بكل ادعاءاته فلا يُستخدم في الأهلية
    claims: Dict[str, List[Feature]] = {}
    for _plugin, feature in pairs:
        claims.setdefault(feature.name, []).append(feature)

    features: Dict[str, Feature] = {}
    for name, group in claims.items():
        merged_ev: List[str] = []
        for claim in group:
            for ev in claim.evidence:
                if ev not in merged_ev:
                    merged_ev.append(ev)
        winner = min(group, key=lambda f: f.source)
        conflicts: List[Dict[str, Any]] = []
        if any(not _values_equal(c.value, winner.value) for c in group):
            # متنازع عليها — كل الادعاءات موثقة بنيتها، والقيمة المعتمدة
            # قاعدة استقرار موثقة (أصغر مصدر معجمياً) لا حقيقة مؤسسة
            conflicts = [
                {"source": c.source, "value": c.value, "evidence": c.evidence}
                for c in sorted(group, key=lambda f: f.source)]
            merged_ev.append(
                "inference:conflicting-values:" + "; ".join(
                    f"{c.source}={c.value!r}"
                    for c in sorted(group, key=lambda f: f.source)))
        sources = "+".join(sorted({c.source for c in group}))
        merged = Feature(name=name, value=winner.value, source=sources,
                         evidence=merged_ev, conflicts=conflicts)
        if len(group) == 1:
            # الثقة كما أعطاها كاشف سمحتها بالواجهة الموثقة — لا تُفقد
            merged.confidence = winner.confidence
        else:
            # المدموج (متتفق أو متعارض): الثقة تُعاد من الأدلة المدموجة
            # المنشورة كلها — قاعدة M7 واحدة باتساق مهما تعدد الكاشفون
            merged.confidence = _CONFIDENCE.calculate(merged_ev)
        merged.detected_at = detected_at
        features[name] = merged

    gaps = list(failures)
    if uro.github_data is None:
        gaps.append("github-data-unavailable: بيانات GitHub (نجوم…) غير "
                    "متاحة في هذا السياق — الأولوية غير معروفة لا مفترضة")
    if "production_capability_usage" not in features \
            and uro.primary_language and uro.primary_language != "Python":
        gaps.append(
            "capability-genome-python-only: مصدر القدرات الموثق (CGP — "
            "R-W2-012) يفحص بايثون؛ لغة غير بايثون بلا استخدام قدرات مكتشف "
            "— الأهلية غير محسومة لا منفية")
    for gap in (uro.capability_usage or {}).get("gaps", []):
        gaps.append(f"capability-genome:{gap}")
    if uro.scan_errors:
        gaps.append(f"scan-errors: {len(uro.scan_errors)}")
    if uro.unread:
        gaps.append(f"unread-files: {len(uro.unread)}")
    if uro.manifest_errors:
        gaps.append(f"manifest-errors: {len(uro.manifest_errors)}")

    return FeatureSet(repository=uro.identity, features=features,
                     detected_at=detected_at,
                     detectors_used=[p.name for p in registry.list_all()],
                     gaps=gaps)


# ---------------------------------------------------------------------------
# M4 — الرسم المعرفي: REPOSITORY-USES-FEATURE (منفصل عن رسم الحضارة
# الموثق سببه: ذلك رسم مستودع/اعتمادية بدلالة مختلفة، وهذا رسم سمات)
# ---------------------------------------------------------------------------

class _Unset:
    def __repr__(self):
        return "UNSET"


_UNSET = _Unset()


class RPPKnowledgeGraph:
    """رسم سمات في الذاكرة — الحواف تحمل ثقة سماتها وأدلتها.

    الحالة الفعّالة تُحدَّث عند إعادة الإضافة: الحواف التي زالت من اللقطة
    الجديدة تُزال (لا يظل المستودع «يستخدم» سمة فارطها)، والتاريخ الكامل
    في أحداث متتبع التطور لا في الرسم.
    """

    def __init__(self):
        self.repositories: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self.features: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[Tuple[str, str, str], str], Dict[str, Any]] = {}

    def add_repository(self, feature_set: FeatureSet) -> None:
        """إضافة/تحديث مستودع — الرسم بمفتاح (المصدر، الفرع) فالحالة
        الفعالة لنسخة واحدة مهما تعددت النسخ المعالجة: النسخة الجديدة
        تستبدل حواف القديمة (لا تتوارثها ولا تضاعفها)، والحواف الزائلة
        تُزال فلا يكذب الرسم، والتاريخ الكامل في أحداث التطور."""
        key = repo_key(feature_set.repository)
        new_names = set(feature_set.features)
        # إزالة حواف النسخ السابقة التي زالت من اللقطة الجديدة
        for (repo, name) in list(self.edges):
            if repo == key and name not in new_names:
                del self.edges[(repo, name)]
                node = self.features.get(name)
                if node and list(key) in node["repositories"]:
                    node["repositories"].remove(list(key))

        self.repositories[key] = {
            "source": key[0], "branch": key[1],
            "version": feature_set.repository[2],
            "detected_at": feature_set.detected_at,
            "feature_names": sorted(new_names)}
        for name, feature in feature_set.features.items():
            node = self.features.setdefault(
                name, {"name": name, "repositories": []})
            self.edges[(key, name)] = {
                "repository": list(key), "feature": name,
                "value": feature.value,
                "confidence": round(feature.confidence, 4),
                "evidence": feature.evidence}
            if list(key) not in node["repositories"]:
                node["repositories"].append(list(key))

    def query(self, feature_name: str, value: Any = _UNSET
              ) -> List[Tuple[str, str, str]]:
        """المستودعات ذات السمة — وقيمتها إن طُلبت (مطابقة واعية بالأنواع)."""
        out = []
        for (repo, name), edge in self.edges.items():
            if name != feature_name:
                continue
            if value is not _UNSET and not _values_equal(edge["value"], value):
                continue
            out.append(repo)
        return sorted(out)

    def repos_with_all(self, feature_names: List[str]) -> List[Tuple[str, str, str]]:
        hits = [set(self.query(f)) for f in feature_names]
        if not hits:
            return []
        return sorted(set.intersection(*hits))

    def to_dict(self) -> Dict[str, Any]:
        return {"repositories": {str(k): v for k, v in self.repositories.items()},
                "features": dict(self.features),
                "edges": {f"{r}|{n}": e for (r, n), e in self.edges.items()}}


def _values_equal(a: Any, b: Any) -> bool:
    """مقارنة قيم واعية بالأنواع — لا تحويل نصوص ولا خلط منطقي/عددي.

    ``True`` لا تساوي ``1`` (خلاف بايثون الافتراضي) و``[1]`` لا تساوي
    ``["1"]`` — النوع جزء من القيمة.
    """
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(
            _values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        return False
    return type(a) is type(b) and a == b


def _is_real(value: Any) -> bool:
    """القيمة الفارغة/الكاذبة/الصفرية/القائمة الفارغة ليست سمة فعلية.

    توثيق مقصود: ``False`` و``0`` و``""`` تعني هنا «غياب قيمة» لا «قيمة
    سالبة» — والغياب غير المحسوم يبقى مجهولاً لا دليلاً (ADR-0002).
    """
    if value is None or value is False or value == "" or value == 0:
        return False
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


# ---------------------------------------------------------------------------
# M5 — محرك التشابه: Jaccard للمفاتيح + cosine فوق متجهات العناصر
# ---------------------------------------------------------------------------

class SimilarityEngine:
    """M5 — تشابه مستودعين من سماتهما: (Jaccard + cosine) / 2 كما وثّقت.

    تصحيح موثق لمثال الوثيقة: كانت تبني متجهات القيم بصدق القيم
    (``1 if value else 0``) فساوى "Python" و"Go" وتشابهت مستودعات بلا سمات
    فعلية — هنا cosine فوق عناصر (مفتاح، قيمة) الحقيقية فقط: القيم الفارغة
    والكاذبة والصفرية ليست سمات فعلية فلا ترفع التشابه، والمقارنة واعية
    بالأنواع (لا تحويل نصوص ولا خلط منطقي/عددي).
    """

    version = "similarity-1.0"

    def find_similar(self, graph: RPPKnowledgeGraph,
                     repo: Tuple[str, str],
                     limit: int = 10) -> List[Dict[str, Any]]:
        repo_features = {name: edge for (r, name), edge in graph.edges.items()
                         if r == repo}
        out = []
        for other in graph.repositories:
            if other == repo:
                continue
            other_features = {name: edge for (r, name), edge in
                              graph.edges.items() if r == other}
            similarity, common, differences = self._compare(
                repo_features, other_features)
            out.append({"repository": list(other), "similarity": similarity,
                        "common_features": common,
                        "differences": differences})
        out.sort(key=lambda x: (-x["similarity"], x["repository"]))
        return out[:limit]

    def _compare(self, a: Dict[str, Any], b: Dict[str, Any]
                 ) -> Tuple[float, List[str], List[str]]:
        keys_a = {k for k, e in a.items() if _is_real(e["value"])}
        keys_b = {k for k, e in b.items() if _is_real(e["value"])}
        union = keys_a | keys_b
        jaccard = len(keys_a & keys_b) / len(union) if union else 0.0

        # cosine فوق متجهات ثنائية لعناصر (مفتاح، قيمة) — القيم الحقيقية فقط
        items_a = {(k, _item_key(a[k]["value"])) for k in keys_a}
        items_b = {(k, _item_key(b[k]["value"])) for k in keys_b}
        dot = len(items_a & items_b)
        cosine = (dot / ((len(items_a) ** 0.5) * (len(items_b) ** 0.5))
                  if items_a and items_b else 0.0)

        common = sorted(keys_a & keys_b)
        value_matches = 0
        differences: List[str] = []
        for k in common:
            if _values_equal(a[k]["value"], b[k]["value"]):
                value_matches += 1
            else:
                differences.append(
                    f"{k}: {a[k]['value']!r} != {b[k]['value']!r}")
        for k in sorted(keys_a - keys_b):
            differences.append(f"{k}: موجود في الأول دون الثاني")
        for k in sorted(keys_b - keys_a):
            differences.append(f"{k}: موجود في الثاني دون الأول")
        return (jaccard + cosine) / 2, common, differences


def _item_key(value: Any) -> str:
    """مفتاح عنصر قابل للهضم — تمثيل القيمة بلا غموض أنواعي."""
    if isinstance(value, (list, tuple)):
        return "list:" + ",".join(_item_key(v) for v in value)
    return f"{type(value).__name__}:{value!r}"


# ---------------------------------------------------------------------------
# M6 — متتبع التطور: لقطات وتغييرات بين نسختين
# ---------------------------------------------------------------------------

class EvolutionTracker:
    """M6 — NEW/REMOVED/CHANGED بين نسختين لمستودع واحد.

    اللقطات لكل نسخة (المصدر+الفرع+الالتزام)، وآخر نسخة لكل (مصدر، فرع)
    هي مرجع المقارنة — فالتطور يقارن التزامين مختلفين فعلاً (انتقال A→B
    أحداث، لا لقطة أولى صامتة)، وإعادة معالجة النسخة نفسها تقارن بلقطتها
    السابقة فلا تنتج أحداثاً ولا تضاعف اللقطات.
    """

    version = "evolution-1.0"

    def __init__(self):
        self.snapshots: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._latest: Dict[Tuple[str, str], Tuple[str, str, str]] = {}
        self.events: List[Dict[str, Any]] = []

    def track(self, feature_set: FeatureSet) -> List[Dict[str, Any]]:
        repo = feature_set.repository
        branch_key = (repo[0], repo[1])
        # الوجود بالمفتاح لا بالقيمة: السمة الصادرة بقيمة False/0/فارغة
        # موجودة كحقيقة موثقة — وتحولها إلى True تغيّر (CHANGED) لا ظهور (NEW)
        new_features = {k: v.value for k, v in feature_set.features.items()}
        changes: List[Dict[str, Any]] = []
        prev_key = self._latest.get(branch_key)
        if prev_key is not None:
            old_features = self.snapshots[prev_key]["features"]
            for k, v in new_features.items():
                if k not in old_features:
                    changes.append({"type": "NEW_FEATURE", "feature": k,
                                    "value": v})
            for k in old_features:
                if k not in new_features:
                    changes.append({"type": "REMOVED_FEATURE", "feature": k})
            for k in set(old_features) & set(new_features):
                if not _values_equal(old_features[k], new_features[k]):
                    changes.append({"type": "CHANGED_FEATURE", "feature": k,
                                    "old_value": old_features[k],
                                    "new_value": new_features[k]})
        # لقطة النسخة — إعادة النسخة نفسها تستبدلها فلا تكرار
        self.snapshots[repo] = {"features": new_features,
                                "detected_at": feature_set.detected_at}
        self._latest[branch_key] = repo
        if changes:
            self.events.append({"repository": list(repo),
                                "detected_at": feature_set.detected_at,
                                "changes": changes})
        return changes

    def is_significant(self, changes: List[Dict[str, Any]]) -> bool:
        return len(changes) >= 3 or any(
            c["type"] == "NEW_FEATURE" for c in changes)


# ---------------------------------------------------------------------------
# M8 — طابور القياس: أهلية بالقيم وأولوية بالنجوم الموثقة إن وجدت
# ---------------------------------------------------------------------------

#: شرط «القدرات» في الأهلية: استخدام فعلي للقدرات في كود الإنتاج —
#: من جينوم القدرات (CGP — R-W2-012): مهارة مدعومة ساكنياً (دليل ملموس:
#: ملف/سطر/رمز) أو قدرة مؤلفة متحققة (تركيب ساكن). ليست أسماء أطر ولا
#: تصريحات اعتماديات ولا نقاط دخول — هذه تصريحات لا استخدام. إشارة
#: ساكنة موثقة الأدلة، لا ادعاء تحقق تشغيلي.
CAPABILITY_FEATURE = "production_capability_usage"


class BenchmarkQueue:
    """M8 — الأهلية الثلاثية بالقيم لا بالمفاتيح، والنجوم مدخل اختياري موثق.

    المجهول ليس صفراً: بلا بيانات GitHub تكون الأولوية UNKNOWN مع فجوة مسماة.
    وفقدان الأهلية يُحدّث الطابور (يُزال العنصر) فلا يبقى مستودع غير مؤهل
    صالحاً للقياس. والتسليم إلى ARI متطلب موثق مؤجل (لا منفذ تشغيلي —
    R-W2-011 محجوب) فيُعلن لا يُدّعى.
    """

    version = "benchmark-queue-1.0"

    def __init__(self):
        self.queue: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def should_benchmark(self, feature_set: FeatureSet) -> Tuple[bool, List[str]]:
        """الأهلية: قدرات مكتشفة + تعريف CI + إطار اختبار مصرّح — كل شرط
        بقيمة حقيقية لا بمجرد مفتاح، والغياب سبب مسمّى لا False صامت."""
        reasons: List[str] = []
        features = feature_set.features
        if not self._established(features, CAPABILITY_FEATURE):
            reasons.append("no-detected-capabilities")
        if not self._established(features, "ci_workflow_definitions_present"):
            reasons.append("no-ci-workflow-definition")
        if not self._established(features, "testing_frameworks_declared"):
            reasons.append("no-testing-framework-declared")
        return (not reasons, reasons)

    @staticmethod
    def _established(features: Dict[str, Feature], name: str) -> bool:
        """الشرط بحقيقة مؤسسة: قيمة حقيقية **غير متنازع عليها** — فالقيمة
        المتعارضة بين كاشفين ليست حقيقة تُبنى عليها أهلية."""
        feature = features.get(name)
        return (feature is not None and not feature.is_contested
                and _is_real(feature.value))

    def priority_for(self, github_data: Optional[Dict[str, Any]]) -> Tuple[str, bool]:
        """الأولوية من النجوم الموثقة — المجهول ليس صفراً (فجوة، لا LOW)."""
        if not github_data or not isinstance(
                github_data.get("stars"), (int, float)) \
                or isinstance(github_data.get("stars"), bool):
            return "UNKNOWN", False
        stars = github_data["stars"]
        if stars > 10000:
            return "HIGH", True
        if stars > 1000:
            return "MEDIUM", True
        return "LOW", True

    def enqueue(self, feature_set: FeatureSet,
                github_data: Optional[Dict[str, Any]] = None
                ) -> Dict[str, Any]:
        key = repo_key(feature_set.repository)
        eligible, reasons = self.should_benchmark(feature_set)
        if not eligible:
            # فقدان الأهلية يُحدّث الطابور — لا يبقى عنصر غير صالح
            removed = self.queue.pop(key, None)
            result: Dict[str, Any] = {"enqueued": False, "reasons": reasons}
            if removed is not None:
                result["removed_no_longer_eligible"] = True
            return result
        priority, stars_known = self.priority_for(github_data)
        item = {"repository": list(key), "version": feature_set.repository[2],
                "priority": priority, "queued_at": feature_set.detected_at,
                "status": "PENDING"}
        self.queue[key] = item   # إعادة الإدراج لا تكرر — النسخة تُستبدل
        return {"enqueued": True, "item": item,
                "gaps": [] if stars_known else
                ["github-data-unavailable: الأولوية UNKNOWN — النجوم غير معروفة"]}


# ---------------------------------------------------------------------------
# قاعدة المعرفة — مالك الحالة عبر الاستدعاءات (رسم + لقطات + طابور مشتركة)
# ---------------------------------------------------------------------------

class RPPKnowledgeBase:
    """الحالة المشتركة: الرسم والتطور والطابور يعيشون هنا لا في كل استدعاء."""

    def __init__(self, registry: Optional[RPPDetectorRegistry] = None):
        self.graph = RPPKnowledgeGraph()
        self.evolution = EvolutionTracker()
        self.queue = BenchmarkQueue()
        self.confidence = ConfidenceEngine()
        self.registry = registry or create_default_registry()
        self.similarity = SimilarityEngine()

    def to_dict(self) -> Dict[str, Any]:
        return {"graph": self.graph.to_dict(),
                "evolution_snapshots": len(self.evolution.snapshots),
                "evolution_events": self.evolution.events,
                "queue": {str(k): v for k, v in self.queue.queue.items()}}


_default_kb: Optional[RPPKnowledgeBase] = None


def get_knowledge_base() -> RPPKnowledgeBase:
    """القاعدة الافتراضية المشتركة — تراكم عبر الاستدعاءات (تشابه/تطور حقيقيان)."""
    global _default_kb
    if _default_kb is None:
        _default_kb = RPPKnowledgeBase()
    return _default_kb


# ---------------------------------------------------------------------------
# الخط — المراحل الثماني بالترتيب المعتمد (M5 داخل المسار)
# ---------------------------------------------------------------------------

class RPPPipeline:
    """M1→M8 بالترتيب — فوق الخط الموحد، والنقص مسمّى في كل مرحلة."""

    def __init__(self, knowledge_base: Optional[RPPKnowledgeBase] = None):
        self.kb = knowledge_base or get_knowledge_base()
        self.normalizer = UniversalNormalizer()

    def process(self, shared: Any, *,
                generated_at: Optional[datetime] = None,
                github_data: Optional[Dict[str, Any]] = None
                ) -> Dict[str, Any]:
        generated_at = generated_at or datetime.now(timezone.utc)
        iso = generated_at.isoformat()

        # M1 — التطبيع (إسقاط فوق الحقائق)
        uro = self.normalizer.normalize(shared, normalized_at=generated_at)
        if github_data is not None:
            uro.github_data = github_data
        # M2/M3 — الكواشف والاستخراج (الدمج حتمي، الثقة من الأدلة المنشورة)
        feature_set = extract_features(
            uro, self.kb.registry, detected_at=iso)
        # M4 — الرسم (الحالة الفعالة تتحدث: الزائل يزول)
        self.kb.graph.add_repository(feature_set)
        # M6 — التطور (اللقطات والأحداث — بين نسختين حقيقيين)
        changes = self.kb.evolution.track(feature_set)
        # M5 — التشابه (استعلام فوق الرسم بمفتاح المستودع — لا يغير حالة)
        similar = self.kb.similarity.find_similar(
            self.kb.graph, repo_key(feature_set.repository))
        # M8 — الطابور (الأهلية بالقيم، وفقدانها يحدث الطابور)
        queue_result = self.kb.queue.enqueue(feature_set, uro.github_data)

        gaps = list(feature_set.gaps)
        gaps.append("ari-delivery-unavailable: التسليم إلى ARI متطلب موثق "
                    "مؤجل — لا منفذ تشغيلي بعد (R-W2-011 محجوب على R-W3-010)")
        gaps.append("marketplace-cli-unavailable: تثبيت/تحديث/إزالة كواشف "
                    "خارجية (سوق الكواشف CLI) يتطلب آلية توزيع حزم — مؤجل "
                    "موثق (سجل العمل 0035)")
        gaps.append("detector-catalog-narrow: الكتالوج الموثق 20+ كاشفاً — "
                    "التسعة المنفذة تغطي حقائق الخط الموحد المتاحة ساكناً "
                    "وإشارة القدرات من CGP؛ التوسيع إضافة أصناف مؤجلة "
                    "(سجل العمل 0035)")
        return {
            "capability": "RPP",
            "rpp_schema_version": RPP_SCHEMA_VERSION,
            "rules_version": RPP_RULES_VERSION,
            "generated_at": iso,
            "universal_repository_object": uro.to_dict(),
            "feature_set": feature_set.to_dict(),
            "similar": similar,
            "evolution_changes": changes,
            "benchmark_queue": queue_result,
            "gaps": gaps,
        }


# ---------------------------------------------------------------------------
# القدرة — مدخل واحد فوق الخط الموحد، حل بالاسم عبر التسجيل
# ---------------------------------------------------------------------------

class RepositoryProcessingPipelineCapability(ICapability):
    """R-W2-013 — خط معالجة المستودعات فوق الخط الموحد.

    الحالة (الرسم/اللقطات/الطابور) مشتركة عبر الاستدعاءات في القاعدة
    الافتراضية — والمعالجة المتكررة لا تضاعف العقد ولا الأحداث.
    """

    name = "RepositoryProcessingPipeline"
    description = ("Runs the 8-stage repository processing pipeline "
                   "(normalize → detect → extract → graph → similarity → "
                   "evolution → confidence → benchmark queue) over the "
                   "unified analysis line")
    skills = ["CloneRepository", "ReadRepository"]
    version = "1.0.0"

    def execute(self, input_data: Any) -> Dict[str, Any]:
        return self._run(input_data, None)

    def execute_with_provider(self, input_data: Any, provider: Any) -> Dict[str, Any]:
        """المادة 7/4 (نمط 0097): المزوّد المختار يصل عبر عقد صريح إلى
        ``analyze_url`` — عند غيابه رفض لا رجوع للإنشاء المحلي في مسار
        المهمة (فرع repo_path بلا مزوّد أصلاً — analyze_path محلي)."""
        if provider is None:
            raise ValueError(
                "execute_with_provider يطلب مزوّداً مختاراً — لا يعمل بلا مزوّد")
        return self._run(input_data, provider)

    def _run(self, input_data: Any, provider: Any) -> Dict[str, Any]:
        if not isinstance(input_data, dict):
            raise ValueError("input must be a dict with url or repo_path")
        url = input_data.get("url")
        repo_path = input_data.get("repo_path") or input_data.get("path")
        if url and repo_path:
            raise ValueError("give either url or repo_path, not both")
        if not url and not repo_path:
            raise ValueError("input needs one of: url, repo_path")
        from capabilities.analysis_service import get_analysis_service
        shared = (get_analysis_service().analyze_url(
            url, input_data.get("branch", "main"), provider=provider) if url
            else get_analysis_service().analyze_path(repo_path))
        pipeline = RPPPipeline(knowledge_base=get_knowledge_base())
        return pipeline.process(
            shared, github_data=input_data.get("github_data"))

    def __init__(self):
        """القيم معلنة كسمات صف (نمط R-W2-007)؛ الباني محفوظ للتوافق (G2)."""
