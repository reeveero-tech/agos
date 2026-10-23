"""واجهة الذكاء الموحدة — ADR-0009 (R-W1-006).

مدخل واحد بثلاثة أنماط سلوكية (**Instant** تنفيذ مباشر عبر السلسلة المتحققة،
**Engineer** خطة فعلية ثم اعتماد صريح لا تنفيذ قبله، **Research** أدلة حقيقية
ومقارنة مسندة معلنة أو تصريح بالتعذر) فوق الخطوط المعتمدة القائمة — لا محرك
جديد. النمط **إلزامي** ويتحقق قبل أي عمل؛ والفجوات مسماة لا مختلقة (البند
PARTIAL — انظر ADR-0009 للحصر).

الاستيرادات النووية كسولة داخل الدوال لتوحيد الهوية (``agos_kernel.X`` هو
``X`` نفسه — ADR-0001) وتجنب أي استيراد دائري.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

__all__ = [
    "IntelligenceMode", "IntelligenceStatus", "EngineeringCandidate",
    "IntelligenceRequest", "IntelligenceResult", "CandidateComparison",
    "ComparisonResult", "IntelligenceInterface", "compare_candidates",
    "COMPARISON_POLICY_ID", "COMPARISON_POLICY_VERSION",
]


class IntelligenceMode(Enum):
    """أنماط الذكاء الثلاثة — إلزامية في الطلب (لا افتراض موثقاً: ADR-0009)."""
    INSTANT = "instant"
    ENGINEER = "engineer"
    RESEARCH = "research"


class IntelligenceStatus(Enum):
    """حالات مخرج الواجهة — كلها صريحة، لا نجاح صورياً.
    ``APPROVED`` اعتماد صريح بلا تنفيذ (التنفيذ بإجازة مستقلة تُستهلك مرة)."""
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECOMMENDATION_UNAVAILABLE = "recommendation_unavailable"


# الفجوات المسماة لكل نمط (ADR-0009) — تُرد في كل مخرج، لا تُختلق
INSTANT_GAPS = [
    # تفسير النية أُغلق للمسار المفسر (0047) — يُرد فقط حيث تعذّر التفسير
    # أو فشل (فشل مسمّى)، لا آلياً في كل نتيجة
    "intent-interpretation",
    # اختيار المزود بمعرفة/خبرة (أُعيدت بسجل العمل 0051 — إغلاق 0050 كان
    # بلا دليل؛ وصُحح إسنادها في 0052): المسار الحي يفاضل بسياسات معلنة
    # (ADR-0006) لا بقاعدة معرفة/خبرة — الفجوة مسماة بغيابها الصادق
    # (أصلها تعليق التنفيذ الأصلي نفسه)؛ نص قبول هذا البند (ADR-0009
    # يسمي فجوة Instant الوحيدة: تفسير القصد) لا يتطلبها ولا يؤجلها
    # صراحةً — ولا يُدَّعى إسنادها لأي محرك رؤية بغير نص
    "knowledge-driven-provider-selection",
]
ENGINEER_GAPS = [
    # مكونات خطة Engineer الآن إسقاط موثق المصدر لما هو كائن (سجل العمل
    # 0043): متطلبات = مواصفة المرسل منقولة حرفياً، وبدائل = مرشحو دليل
    # القرار المقيّمون، وتكلفة = المدة المعلنة في الخطة حرفياً. الفجوات
    # المسماة أدناه هي ما تبقى بلا اشتقاق صادق — تُرد في كل مخرج لا تُخفى:
    "engineering-plan-requirements-analysis",  # نقل حرفي فقط — لا تحليل/تفصيل متطلبات
    "engineering-plan-risks",                 # لا تقييم مخاطر
    "engineering-plan-design-alternatives",   # بدائل الاختيار منقولة — لا بدائل تصميم مقارنة
    "engineering-plan-cost-estimate",         # مدة معلنة حرفياً — لا تقدير تكلفة مقيس
    "engineering-plan-architecture",          # المعمارية القائمة تحليل لما هو كائن لا تصميم
]
RESEARCH_GAPS = [
    # اتساع البحث أُغلق (سجل العمل 0049 + تصحيح 0050): البحث متعدد المصادر
    # عبر evidence_paths بإثبات لكل مصدر لكل مرشح — لا اتحاد؛ واختلاف
    # المستودعات اختلاف موثق لا تعارض (التعارض الحقيقي يتطلب الموضوع
    # والسياق نفسيهما وادعاءين متنافسين مسندين)؛ وغياب دليل مصدر مسمّى؛
    # والسؤال يقود جمع الأدلة **والمقارنة** (مفاهيمه ← فئات الحقائق ←
    # حزمة المقارنة نفسها — تغيير السؤال يغيّر النتيجة حيث توجد قرينة)
    "ari-benchmarks",                    # تسليم ARI متطلب موثق مؤجل (غياب التسليم وحده المثبت)
    "success-and-experience-data",       # لا بيانات نجاح/تجارب سابقة
]


# ===============================================================
# عقد Research — المرشح والمقارنة
# ===============================================================
@dataclass
class EngineeringCandidate:
    """مرشح للمقارنة — تقنياته **معلنة من مقدم الطلب** (caller-provided):
    ليست حقائق أثبتها التحليل، وتُوسَم كذلك في المخرج."""
    id: str
    name: str
    technologies: List[str] = field(default_factory=list)


@dataclass
class CandidateComparison:
    """نتيجة مرشح واحد في المقارنة — القيمة مثبتة بالأدلة (التقنيات المتقاطعة)."""
    candidate_id: str
    score: int
    matched_technologies: tuple        # الدليل: أسماء تقنيات المرشح الموجودة في الحزمة المكتشفة
    order: int                          # ترتيب الإدراج — قاعدة كسر التعادل المعلنة
    exclusion_reason: Optional[str] = None


@dataclass
class ComparisonResult:
    """مخرج المقارنة — قابل للتتبع إلى الأدلة المستخدمة. التقنيات المعلنة
    محفوظة بمصدرها الصريح (``caller-provided``) **مفصولة** عن الحقائق
    المكتشفة (التي تحمل مصدر الخدمة المعتمدة لكل حقل)."""
    policy_id: str
    policy_version: str
    ranked: List[CandidateComparison]   # كل المرشحين المقيمين مرتبين
    best: Optional[CandidateComparison]  # None عند تقاطع الجميع صفراً — لا توصية بلا مواءمة
    declared_technologies: Dict[str, List[str]] = field(default_factory=dict)
    declared_source: str = "caller-provided"
    evidence_snapshot: Dict[str, Any] = field(default_factory=dict)


COMPARISON_POLICY_ID = "repository-stack-alignment"
COMPARISON_POLICY_VERSION = "1.0"


def _evidence_facts(evidence: Any) -> Dict[str, Any]:
    """الحقائق **وأدلة اكتشافها كما توفرها الخدمة المعتمدة فعلاً** — بلا كاشف
    موازٍ وبلا اختلاق حقول: قياس اللغة من ``LanguageStat`` (ملفات/أسطر)،
    ودليل الإطار من سجلات ``Evidence`` (الاعتمادية والملف والنظام والنطاق)،
    وبيئات التشغيل أسماء فقط **لا توفر الخدمة دليلاً لكل حقيقة منها —
    يُصرَّح بغيابه**."""
    stack = getattr(evidence, "stack", None)
    language_stats = getattr(evidence, "code_languages", None) or {}
    languages = {}
    for language, stat in language_stats.items():
        languages[str(language)] = {
            "files": getattr(stat, "files", None),
            "lines": getattr(stat, "lines", None),
        }
    framework_evidence: Dict[str, Any] = {}
    for record in (getattr(stack, "evidence", None) or []):
        name = str(getattr(record, "framework", ""))
        framework_evidence.setdefault(name, []).append({
            "dependency": getattr(record, "dependency", ""),
            "manifest": getattr(record, "manifest", ""),
            "ecosystem": getattr(record, "ecosystem", ""),
            "scope": getattr(record, "scope", ""),
            "counted": getattr(record, "counted", None),
        })
    return {
        "languages": languages,                      # القياس الفعلي لكل لغة
        "frameworks": framework_evidence,             # سجلات Evidence لكل إطار
        "runtimes": {
            "names": list(getattr(stack, "runtimes", None) or []),
            "per_fact_provenance": "لا توفره الخدمة المعتمدة — غياب مصرَّح",
        },
    }


def _detected_stack_names(evidence: Any,
                           fact_categories: Optional[List[str]] = None) -> tuple:
    """أسماء حزمة المستودع المكتشفة (مطبَّعة) — من الحقول المعتمدة أعلاه.
    المطابقة غير حساسة لحالة الأحرف؛ والتطبيع وإزالة التكرار قبل التقاطع
    فلا تحسّن التكرارات أو اختلاف الحالة الدرجة.

    ``fact_categories`` (سجل العمل 0050): حزمة المقارنة تُبنى من فئات
    سؤال البحث فقط — السؤال يقود **المقارنة** لا العرض وحده؛ وما خارج
    الفئات يُستبعد من الحزمة (استبعاد موسوم في اللقطة لا حذف صامت)."""
    names = set()
    include_languages = fact_categories is None or "languages" in fact_categories
    include_frameworks = fact_categories is None or "frameworks" in fact_categories
    include_runtimes = fact_categories is None or "runtimes" in fact_categories
    if include_languages:
        for language in _evidence_facts(evidence)["languages"]:
            names.add(str(language).strip().lower())
    stack = getattr(evidence, "stack", None)
    if include_frameworks:
        for item in (getattr(stack, "frameworks", None) or []):
            names.add(str(item).strip().lower())
    if include_runtimes:
        # السلوك الكامل عند غياب الترشيح (سجل العمل 0051 — انحدار 0050):
        # runtimes كان متاحاً قبل الترشيح وبقي معه إلا عند استبعاد مقصود
        for item in (getattr(stack, "runtimes", None) or []):
            names.add(str(item).strip().lower())
    return tuple(sorted(names))


def compare_candidates(candidates: List[EngineeringCandidate],
                       evidence: Any,
                       fact_categories: Optional[List[str]] = None) -> ComparisonResult:
    """السياسة المتخصصة المعلنة (ADR-0009): **مواءمة حزمة المستودع** — ليست
    تفويضاً لخط القرار ولا توصية «أفضل تصميم» عموماً.

    المعيار ومصدر دليله (واحد، حقيقي): تقاطع تقنيات المرشح المعلنة مع حزمة
    المستودع المكتشفة فعلاً. الدرجة = حجم التقاطع؛ التعادل يُكسر بترتيب
    الإدراج **بين ذوي مواءمة مثبتة فقط**؛ والتقنية غير المكتشفة ليست فشلاً
    بل قيمة أدنى معللة؛ والمرشح بلا تقنيات معلنة يُستبعد بمسوّى مسمّى.
    **تقاطع الجميع صفراً: لا توصية** — اختيار الأول هنا لا يصنع توصية مسندة.

    ``fact_categories`` (سجل العمل 0050): السؤال يقود المقارنة — الحزمة
    تُبنى من فئات سؤال البحث فقط، فتغيير السؤال يغيّر أدلة المقارنة
    ونتيجتها حيث توجد قرينة مميّزة (مختبر)."""
    
    stack = set(_detected_stack_names(evidence, fact_categories))
    declared: Dict[str, List[str]] = {}
    comparisons: List[CandidateComparison] = []
    for index, candidate in enumerate(candidates):
        declared[candidate.id] = list(candidate.technologies)
        if not candidate.technologies:
            comparisons.append(CandidateComparison(
                candidate_id=candidate.id, score=0, matched_technologies=(),
                order=index, exclusion_reason="no-declared-technologies"))
            continue
        # تطبيع وإزالة تكرار قبل التقاطع — مجموعة معيارية واحدة لكل مرشح:
        # التكرار أو اختلاف الحالة لا يحسّن الدرجة
        normalized = sorted({str(t).strip().lower()
                            for t in candidate.technologies})
        matched = tuple(sorted(t for t in normalized if t in stack))
        comparisons.append(CandidateComparison(
            candidate_id=candidate.id, score=len(matched),
            matched_technologies=matched, order=index))
    # الترتيب: المواءمة الأعلى أولاً ثم ترتيب الإدراج (قاعدة معلنة)
    ranked = sorted(comparisons, key=lambda c: (-c.score, c.order))
    best = ranked[0] if (ranked and ranked[0].score > 0) else None
    return ComparisonResult(
        policy_id=COMPARISON_POLICY_ID,
        policy_version=COMPARISON_POLICY_VERSION,
        ranked=ranked,
        best=best,
        declared_technologies=declared,
        declared_source="caller-provided",
        evidence_snapshot={
            "detected": _evidence_facts(evidence),
            "detected_stack": list(_detected_stack_names(evidence)),
        })


# ===============================================================
# الطلب والمخرج
# ===============================================================
@dataclass
class IntelligenceRequest:
    """طلب الذكاء — النمط إلزامي (بلا نمط أو بنمط غير صالح: خطأ صريح قبل أي
    عمل، لا تحويل صامت). مواصفة المهمة (Instant/Engineer) أو مصدر الأدلة
    والمرشحون (Research)."""
    mode: Optional[IntelligenceMode] = None
    mission: Optional[Dict[str, Any]] = None      # {name, description, capability, parameters}
    question: Optional[str] = None                # Research
    evidence_path: Optional[str] = None           # Research: مسار المستودع
    candidates: Optional[List[EngineeringCandidate]] = None  # Research
    #: طلب طبيعي (Instant/Engineer): يُفسر بالمفسر المعلن (معجم ثنائي +
    #: جدول إيفاء مُثبت بالمخرجات) — الحقل أُضيف **بعد** الحقول القائمة
    #: كلها فالمنشئ الموضعي القديم لا يتأثر (سجل العمل 0047)
    natural_text: Optional[str] = None
    #: مصادر أدلة متعددة (Research، سجل العمل 0049): بحث متعدد المصادر —
    #: إثبات لكل مصدر لكل مرشح (لا اتحاد)؛ أُضيف في النهاية حفظاً
    #: للتوافق الموضعي
    evidence_paths: Optional[List[str]] = None
    #: دعاوى صريحة مسندة عن المصادر (سجل العمل 0054): كل دعوى تحمل
    #: المسار والخاصية والقيمة (أثبت/أنكر صراحةً) ودليلها — تصل من مدخل
    #: الواجهة فعلًا (تُطابق بمسار المصدر)؛ التحليل الحالي لا ينتجها،
    #: والدعاوى المتنافاة عن الخاصية نفسها لمسار واحد تُعرض تعارضاً
    source_claims: Optional[List[Dict[str, Any]]] = None


@dataclass
class IntelligenceResult:
    """مخرج الواجهة — الحالة صريحة دائماً والفجوات مسماة فيه."""
    mode: IntelligenceMode
    status: IntelligenceStatus
    mission_id: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    decision_records: List[Any] = field(default_factory=list)
    plan: Any = None
    approval_id: Optional[str] = None
    comparison: Optional[ComparisonResult] = None
    evidence_snapshot: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)
    #: مكونات خطة Engineer — إسقاط موثق المصدر لما هو كائن (R-W1-006):
    #: لا تُعرض إلا حيث توجد خطة واختيار حقيقيان؛ الفشل المبكر يتركها None.
    #: الحقل أُضيف **بعد** الحقول القائمة كلها — المنشئ الموضعي القديم لا يتأثر
    engineering_plan: Optional[Dict[str, Any]] = None


# ===============================================================
# نواة مُتحققة عند حد الاستدعاء (ADR-0009)
# ===============================================================
class _VerifyingCore:
    """نواة مُغلِّفة: تتحقق **عند حد الاستدعاء الفعلي** — قبل مرور العمل إلى
    النواة الداخلية — أن العمل المارّ هو العمل الموافق عليه **كاملاً**: هوية
    صاحب الدالة، **والدالة نفسها** (تبديل ``execute`` على الكائن نفسه لا يمر)،
    **والمعاملات الموافق عليها** (تغيير المعاملات داخل حل الأنبوب لا يمر).
    ``expected=None`` يعني **بلا حراسة** (Instant بلا حد اعتماد — مفصول عن
    Engineer الذي يُرفض بلا عمل معتمد أصلاً)."""

    def __init__(self, inner: Any):
        self._inner = inner
        # العمل الموافق عليه: (صاحب الدالة، الدالة نفسها، المعاملات)
        self.expected: Any = None
        #: عدّاد الاستدعاءات التي عبرت إلى النواة الإنتاجية فعلاً (سجل
        #: العمل 0050) — يُثبت صفر تنفيذ قبل الإجازة وواحدية التنفيذ
        self.invocations: int = 0

    @staticmethod
    def _work_identity(func):
        return getattr(func, "__func__", func)

    def invoke_sync(self, func, *args, **kwargs):
        expected = self.expected
        if expected is not None:
            owner, function, parameters = expected
            bound = getattr(func, "__self__", None)
            if (bound is not owner
                    or self._work_identity(func) is not function):
                from agos_kernel.execution.engine import InvocationOutcome
                return InvocationOutcome(error=RuntimeError(
                    "العمل المار إلى النواة ليس العمل الموافق عليه "
                    "(ADR-0009): رُفض استدعاء دالة لم تُعتمد"))
            if not (len(args) == 1 and args[0] == parameters):
                from agos_kernel.execution.engine import InvocationOutcome
                return InvocationOutcome(error=RuntimeError(
                    "المعاملات المارّة إلى النواة ليست المعاملات الموافق "
                    "عليها (ADR-0009): رُفض تنفيذ بمعاملات لم تُعتمد"))
        self.invocations += 1          # استدعاء عبر إلى النواة الإنتاجية فعلاً
        return self._inner.invoke_sync(func, *args, **kwargs)


# ===============================================================
# حارس حد الاعتماد (ADR-0009) — داخل الواجهة؛ حزمة الاعتماد لم تُمس
# ===============================================================
def _plan_fingerprint(plan: Any) -> tuple:
    """بصمة كاملة لمحتوى الخطة — **كل حقولها الفعلية بلا تحويلات تمحو
    اختلاف المحتوى** (mission_id والخطوات والمدة الخام والقدرات والمهارات):
    تعديل الخطة نفسها مع بقاء المعرّف والعمل والمعاملات لا يمر (ADR-0009)."""
    return (
        str(getattr(plan, "mission_id", "") or ""),
        tuple(getattr(plan, "steps", ()) or ()),
        getattr(plan, "estimated_duration_ms", None),   # القيمة الخام
        tuple(getattr(plan, "required_capabilities", ()) or ()),
        tuple(getattr(plan, "required_skills", ()) or ()),
    )


def _analysis_content_digest(shared: Any) -> tuple:
    """هوية محتوى من فهرس التحليل الفعلي مع **موثوقيتها**: (هوية، موثوقة؟) —
    الموثوقة تتطلب هاش محتوى فعلياً لكل ملف غير مجلد؛ سياستنا
    (hash_predicate=None) لا تهشّ أصلاً فالهوية عندئذ بيانات وصفية فقط
    (مسار+حجم) قد تتطابق مع محتوى مختلف بنفس الطول — فلا يُدَّعى إثبات
    توافق السياق بها (سجل العمل 0053). لا بصمة تغيّر معتمدة بعد (ADR-0005)."""
    import hashlib
    files = [f for f in (getattr(shared, "files", None) or [])
             if not getattr(f, "is_dir", False)]
    parts = []
    hashed = 0
    for f in sorted(files, key=lambda x: str(getattr(x, "path", ""))):
        sha = getattr(f, "sha256", "") or ""
        if sha:
            hashed += 1
        parts.append("{}:{}:{}".format(getattr(f, "path", ""),
                                       getattr(f, "size_bytes", 0), sha))
    digest = hashlib.sha256(
        "|".join(parts).encode("utf-8")).hexdigest()[:16]
    reliable = bool(files) and hashed == len(files)
    return digest, reliable


#: مسارات المنتجين المتحقق منها فعلاً — من استدعاءات execute نفسها
#: (سجل العمل 0053): RA من capabilities/__init__.py (analyze_url ←
#: _build_dna بstack_detection.project_dependencies/dependency_records ←
#: framework_evidence من shared.stack.evidence)؛ وRPP من rpp.py
#: (analyze_url/path ← RPPPipeline.process ← normalizer.normalize → uro)
_VERIFIED_PRODUCER_PATHS: Dict[str, Dict[str, Any]] = {
    "RepositoryAnalysis": {
        "producers": {
            "frameworks": "get_analysis_service().analyze_url → "
                          "shared.stack (stack_detection.detect_stack "
                          "بسجلات Evidence) → _build_dna(stack=…) ← "
                          "dna.frameworks + dna.framework_evidence = "
                          "[e.to_dict() for e in shared.stack.evidence]",
            "languages": "analyze_url → shared.code_languages "
                         "(LanguageStat المقيسة) ← dna.languages + "
                         "_language_breakdown_of(shared) ← "
                         "stack_detection.language_breakdown ← "
                         "dna.language_stats",
            "dependencies": "analyze_url → shared.stack ← _build_dna: "
                            "stack_detection.project_dependencies(stack) "
                            "→ dna.dependencies + dependency_records → "
                            "dna.dependency_details",
        },
        "data_flow": [
            "url + branch",
            "get_analysis_service().analyze_url (خط ADR-0005)",
            "stack_detection (detect_stack + project_dependencies + "
            "language_breakdown) — منتج الحقائق وأدلتها",
            "RepositoryAnalysisCapability.execute → _build_dna ← "
            "RepositoryDNA (frameworks/languages/dependencies/"
            "framework_evidence/language_stats)",
        ],
    },
    "RepositoryProcessingPipeline": {
        "producers": {
            "frameworks": "get_analysis_service().analyze_url/analyze_path "
                          "→ RPPPipeline.process → normalizer.normalize "
                          "(shared) → uro.frameworks + uro.framework_evidence",
            "languages": "process → normalizer.normalize → "
                         "uro.all_languages + uro.language_stats",
            "dependencies": "process → normalizer.normalize → "
                            "uro.dependencies",
        },
        "data_flow": [
            "url أو repo_path",
            "get_analysis_service().analyze_url/analyze_path (خط ADR-0005)",
            "RPPPipeline.process: normalizer.normalize (إسقاط uro) + "
            "extract_features + kb.graph/evolution/similarity/queue "
            "(الحالة المشتركة — تُستدعى فعلاً)",
            "uro (frameworks/dependencies/all_languages/"
            "framework_evidence/language_stats)",
        ],
    },
}


def _design_tradeoffs(name: str, required_concepts: List[str]) -> List[str]:
    """مفاضلات تصميمية معلنة لكل بديل — من عقده وحقائق الكود الفعلية
    (سجل العمل 0051): لا تقييمات عامة بل ما يميز هذا التصميم للمتطلبات."""
    if name == "RepositoryAnalysis":
        return [
            "يغطي المفاهيم في كائن DNA واحد بحقول معلنة وسجلات أدلة أطر "
            "(framework_evidence: الاعتمادية/البيان/النطاق) — ويطلب "
            "GenerateDNA فوق القراءة (تبعية معلنة في عقده)",
        ]
    if name == "RepositoryProcessingPipeline":
        return [
            "خط 8 مراحل فوق الخط الموحد بحالة مشتركة عبر الاستدعاءات "
            "(الرسم/اللقطات/الطابور — معلنة في عقده): آثار جانبية مشتركة "
            "تُقيَّد كمخاطر تصميم",
            "يحمل أدلة كشف لكل إطار (framework_evidence بمسارات الملفات) "
            "وسمات أوسع من المطلوب (feature_set/similar/evolution) — أوسع "
            "من المطلوب وتعقيداً أعلى مقابل أدلة أغنى",
        ]
    if name == "RepositoryDNAGeneration":
        return [
            "بصمة خفيفة dict مع fingerprint محسوب — لا يحمل dependencies "
            "(package_managers ليس dependencies) ولا سجلات أدلة",
        ]
    return []


def _mission_field(mission_spec: Any, field: str) -> str:
    """قراءة حقل من مواصفة مهمة — قاموساً كانت أو كائن Mission."""
    if isinstance(mission_spec, dict):
        return str(mission_spec.get(field, "") or "")
    return str(getattr(mission_spec, field, "") or "")


def _engineering_plan(mission: Any, plan: Any,
                       decision_records: List[Any],
                       interpreted: Optional[Dict[str, Any]] = None,
                       measured_executions: Optional[List[Dict[str, Any]]] = None
                       ) -> Dict[str, Any]:
    """مكونات خطة Engineer — إسقاط موثق المصدر لما هو كائن فعلاً (R-W1-006).

    لا اختراع: كل مكوّن يُشتق من واقع قائم (مواصفة المرسل، الخطة، دليل
    القرار) ويحمل مصدره بصدقه، وما لا اشتقاق له يبقى فجوة مسماة في
    ``gaps`` لا قيمة مختلقة هنا. المكونات المعروضة مربوطة ببصمة عميقة
    محافظة على الأنواع (``_engineering_plan_fingerprint``) تُفحص عند
    بوابتي الاعتماد والتنفيذ (سجل العمل 0044).

    المسار المفسر من الطلب الطبيعي (سجل العمل 0048): المكونات تُشتق من
    النية المفسرة **قبل الاختيار** — المتطلبات من نص المستخدم، والبدائل
    مرشحو الإيفاء تقارن عبر دليل القرار القائم، والمخاطر والتكلفة المقيسة
    والمعمارية مشتقة بأسانيدها المعلنة (لا تُغلق الفجوات إلا بما اشتُق
    فعلاً — والتكلفة لا تُغلق إلا بقياس موجود).
    """
    if interpreted is not None:
        return _interpreted_engineering_plan(
            mission, plan, decision_records, interpreted,
            measured_executions or [])
    # المتطلبات: مواصفة المرسل منقولة حرفياً بوسم مصدرها — ليست تحليل متطلبات
    requirements: List[Dict[str, Any]] = []
    for ref, value in (("mission.name", getattr(mission, "name", "")),
                      ("mission.description", getattr(mission, "description", "")),
                      ("mission.capability", getattr(mission, "capability", ""))):
        if value not in ("", None):
            requirements.append({"ref": ref, "value": value,
                                 "source": "caller-provided"})
    for key, value in (getattr(mission, "parameters", None) or {}).items():
        requirements.append({"ref": f"mission.parameters.{key}",
                             "value": value, "source": "caller-provided"})
    # البدائل: مرشحو الاختيار كما قُيّموا فعلاً في دليل القرار — بدرجاتهم
    # واستبعادهم واختيارهم وكسر تعادلهم؛ بدائل اختيار قدرة موثقة لا بدائل
    # تصميم/معمارية مقارنة (تلك فجوة مسماة). دليل غير قابل للإسقاط يوسم
    # بصدقه ولا يُستبدل
    alternatives: Optional[Dict[str, Any]] = None
    record = decision_records[0] if decision_records else None
    if record is not None:
        projected = record.to_dict() if hasattr(record, "to_dict") else None
        if projected is not None:
            alternatives = {
                **projected,
                # نوع السجل الأصلي محفوظ — لا يُستبدل بوسم المكوّن
                "record_kind": projected.get("kind"),
                "kind": "capability-selection",
                "note": "مرشحو الاختيار المقيّمون في دليل القرار — ليست بدائل تصميم/معمارية مقارنة",
            }
        else:
            alternatives = {
                "kind": "capability-selection",
                "note": "دليل قرار غير قابل للإسقاط من هذا النوع — انظر decision_records",
                "record_type": type(record).__name__,
            }
    # التكلفة: ما هو معلن في الخطة فعلاً — مدة مقدرة حرفياً في المخطط
    # لا قياساً؛ لا يُدّعى تقدير تكلفة
    cost = {
        "estimated_duration_ms": getattr(plan, "estimated_duration_ms", None),
        "source": "declared-literal",
        "measured": [],               # لا قياس — الفجوة مسماة
    }
    return {
        "requirements": requirements,
        "alternatives": alternatives,
        "risks": None,               # لا تقييم مخاطر — الفجوة مسماة
        "cost": cost,
        "architecture_design": None,  # تحليل لما هو كائن لا تصميم — الفجوة مسماة
    }


def _interpreted_engineering_plan(
        mission: Any, plan: Any, decision_records: List[Any],
        interpreted: Dict[str, Any],
        measured_executions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """مكونات خطة المسار المفسر — اشتقاق موثق الأسناد من نية مفسرة قبل
    الاختيار (سجل العمل 0048). لا تحقق دائري: المتطلبات من نص المستخدم،
    والبدائل من جدول الإيفاء المُثبت بالمخرجات، والمقارنة من دليل القرار
    القائم، والمخاطر/التكلفة/المعمارية مشتقة بأسانيدها المعلنة."""
    from intelligence import intent as intent_module
    interpretation = interpreted["interpretation"]
    selected = interpreted["selected"]

    # ---- المتطلبات: مشتقة من نص المستخدم قبل أي اختيار ----
    requirements: List[Dict[str, Any]] = [
        {"ref": "natural_text", "value": interpreted["natural_text"],
         "source": "user-text-verbatim"}]
    for concept in interpretation.required_concepts:
        matched = next((t for c, t in interpretation.matched_terms
                       if c == concept), "")
        requirements.append({
            "ref": f"intent.required.{concept}", "value": concept,
            "evidence": f"مصطلح مطابق: {matched}",
            "source": "interpreted-from-natural-text"})
    for concept in interpretation.negated_concepts:
        requirements.append({
            "ref": f"intent.negated.{concept}", "value": concept,
            "evidence": "نُفي صراحةً في الطلب — استبعاد لا متطلب",
            "source": "interpreted-from-natural-text"})
    for key, value in interpretation.artifacts.items():
        requirements.append({
            "ref": f"intent.artifact.{key}", "value": value,
            "evidence": "مستخرج نصياً من الطلب — لا تخمين",
            "source": "extracted-from-text"})

    # ---- البدائل: مرشحو الإيفاء والمقارنة من دليل القرار القائم ----
    comparison = interpreted["comparison"]
    projected = (comparison.to_dict() if hasattr(comparison, "to_dict")
                 else {"record_type": type(comparison).__name__})
    candidate_rows = []
    contracts = interpreted.get("contracts", {})
    for name in interpreted["alternatives"]:
        fulfill_carriers = {}
        for concept in interpretation.required_concepts:
            entry = intent_module.FULFILLMENT.get(concept, {}).get(name)
            if entry:
                fulfill_carriers[concept] = entry[0]
        eval_row = next((e for e in projected.get("candidates", [])
                         if e.get("name") == name), None)
        contract = contracts.get(name, {})
        candidate_rows.append({
            "name": name,
            "design_approach": contract.get("description", ""),
            # مهارات معلنة مطلوبة — تبعيات لا مراحل مثبتة
            "required_skills_declared": contract.get("skills", []),
            "design_tradeoffs": _design_tradeoffs(
                name, interpretation.required_concepts),
            "fulfillment_evidence": fulfill_carriers,   # حامل المخرج الفعلي
            "evaluation": eval_row,                    # درجة دليل القرار
        })
    alternatives = {
        "kind": "design-alternatives-compared",
        "policy": "live-capability-resolution (دليل القرار القائم وسياسته الحية)",
        "required_skills": interpreted["required_skills"],
        "skill_source": "CONCEPT_SKILLS المعلن — اشتقاق من المفاهيم لا من قدرة",
        "candidates": candidate_rows,
        "selection": {
            "selected": selected,
            "tie_break": projected.get("tie_break"),
            "policy_id": (projected.get("policy") or {}).get("policy_id"),
            "note": "تعادل إيفاء حقيقي: كل المرشحين مُثبت إيفاؤهم بحوامل "
                    "المخرجات فدرجاتهم متساوية — الاختيار بقاعدة معلنة "
                    "(ترتيب التسجيل المستقر) لا بأفضلية من عدد التبعيات "
                    "المطلوبة؛ التصميمان معروضان بمفاضلاتهما والمعتمِد "
                    "يرى ويميّز (مثلاً «بصمة DNA») أو يرفض",
        },
        "record": projected,
        "note": "مرشحو الإيفاء المثبت بالمخرجات قورنوا بدليل القرار القائم",
    }

    # ---- المخاطر: مشتقة من أسانيد واقعية للتصميم المختار ----
    risks: List[Dict[str, Any]] = []
    url = interpretation.artifacts.get("url", "")
    if url.startswith("http"):
        risks.append({
            "risk": "اعتماد على الشبكة — المصدر رابط بعيد",
            "evidence": f"المصدر المستخرج نصياً: {url}",
            "impact": "فشل الوصول يفشل المهمة قبل أي تحليل",
            "mitigation": "سياسة الاستنساخ الآمن ترفض المخفي والسطحي؛ المصدر "
                          "المحلي بديل بلا شبكة",
            "mitigation_verification": "فشل الاستنساخ يظهر خطأً مسمى في أحداث "
                                       "التنفيذ (execution_failed)",
            "probability": None})
    risks.append({
        "risk": "صلاحية معاملات غير مثبتة — ما لم يذكره المستخدم (فرع/عمق) "
                "يبقى بقيمة القدرة المعلنة",
        "evidence": "المفسر يستخرج المصادر نصياً فقط ولا يخمّن معاملات",
        "impact": "قد تختلف النتيجة عن توقع المستخدم إن كانت القيمة المعلنة "
                  "غير المقصودة",
        "mitigation": "الخطة المعروضة للاعتماد تُظهر المعاملات كما استخرجت",
        "mitigation_verification": "المعتمِد يرى mission.parameters في الخطة "
                                   "قبل الإجازة",
        "probability": None})
    # عينات مفصولة (سجل العمل 0051+0052): مجموعة المقارنة مجموعة واحدة —
    # الوضع (engineer) والمدخل (معاملات الطلب نفسها) والقدرة؛ تنفيذ بمدخل
    # آخر لا يدخل وسيطها ولا يغلق فجوتها؛ الشروط المعروضة معروضة فعلاً
    input_parameters = dict(getattr(mission, "parameters", None) or {})
    comparable = [e for e in measured_executions
                  if e.get("state") == "completed"
                  and e.get("mode") == "engineer"
                  and dict(e.get("parameters") or {}) == input_parameters]
    completed = comparable
    if not completed:
        risks.append({
            "risk": "لا تنفيذ مقيس لهذه القدرة بهذا المدخل في هذا الوضع — "
                    "عدم يقين في المدة، ليس دليل فشل",
            "evidence": "سجل التنفيذات (rt.missions بإسناد المعرّف) لا يحوي "
                        "تنفيذاً مكتملاً بنفس معاملات هذا الطلب في وضع "
                        "engineer",
            "impact": "تقدير المدة يبقى معلناً لا مقيساً",
            "mitigation": "أول تنفيذ لهذا المدخل يُقاس ويُسند فيغلق الفجوة "
                          "لطلبات المدخل نفسه فقط",
            "mitigation_verification": "المدة المقيسة تظهر في سجل rt.missions "
                                       "بعد التنفيذ بشروط عينتها",
            "probability": None})

    # ---- التكلفة: مدة تنفيذ مقيسة من سجل التنفيذات، وإلا معلنة حرفياً ----
    if completed:
        ordered = sorted(e["duration_ms"] for e in completed)
        n = len(ordered)
        median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1]
                                              + ordered[n // 2]) // 2
        modes = sorted({e["mode"] for e in completed})
        sources = sorted({e.get("source", "") for e in completed})
        inputs = sorted({str(e.get("parameters", {}).get("url", ""))
                         for e in completed})
        versions = sorted({e.get("capability_version", "")
                           for e in completed})
        cost = {
            "n": n, "median_ms": median,
            "observed_min_ms": ordered[0], "observed_max_ms": ordered[-1],
            "unit": "measured-execution-duration",
            "conditions": {"capability": selected, "state": "completed",
                           "modes": modes, "record_source": sources,
                           "inputs": inputs, "capability_versions": versions},
            "unmeasured_conditions": {
                "environment": "غير مقيس — مجهول معلن",
                "load": "غير مقيس — مجهول معلن",
            },
            "note": "مدة تنفيذ مقيسة (وسائط وعينة مدى ملحوظ) — لا تكلفة "
                    "مالية ولا ادعاء شمول؛ البيئة والحمل مجهولان معلنان "
                    "لا يُدّعى قياسهما",
            "source": "measured",
        }
    else:
        cost = {
            "estimated_duration_ms": getattr(plan, "estimated_duration_ms", None),
            "source": "declared-literal",
            "measured": [],
            "note": "لا تاريخ تنفيذ مقيس لهذه القدرة بعد — الفجوة مسماة "
                    "(engineering-plan-cost-estimate)",
        }

    # ---- المعمارية: منتجون متحققون من مسارات تنفيذ فعلية (سجل العمل
    # 0053 — تصحيح 0052): الربط خاص بالقدرة المتحقق من مسارها (استدعاءات
    # execute نفسها لا وجود helpers) — وما لم يُتحقق لا يُورَّث وصف غيره
    contract = interpreted.get("contracts", {}).get(selected, {})
    carriers = {
        concept: intent_module.FULFILLMENT.get(concept, {}).get(
            selected, ([], False))[0]
        for concept in interpretation.required_concepts}
    verified = _VERIFIED_PRODUCER_PATHS.get(selected)
    if selected == "RepositoryAnalysis":
        boundary = ("عقد مخرج RA؛ له كاش DNA معلن بمفتاح الالتزام "
                    "(_dna_cache في execute — مراجعة جديدة مفتاح جديد "
                    "فلا يُخدم نتيجة متقادمة)")
    elif selected == "RepositoryProcessingPipeline":
        boundary = ("عقد مخرج RPP؛ **لها وحدها** حالة مشتركة عبر "
                    "الاستدعاءات (kb.graph/kb.evolution/kb.queue — "
                    "تُستدعى فعلاً في process) تُقيَّد كمخاطر تصميم خاصة "
                    "بها")
    else:
        boundary = "عقد مخرج المختار"
    architecture_design = {
        "kind": "proposal",
        "derived_from": "requirements (before selection) + chosen contract",
        "declared_design": contract.get("description", ""),
        "components": [
            {
                "component": "استنساخ وقراءة المصدر",
                "responsibility": "جلب المصدر المستخرج نصياً وقراءته بأمان",
                "interface": "url → ملفات وحقائق خام",
                "boundaries": "خدمة التحليل المعتمدة (ADR-0005) — لا كاشف "
                             "موازٍ ولا شبكة لمدخل محلي",
                "declared_dependencies": [
                    s for s in contract.get("skills", [])
                    if s in ("CloneRepository", "ReadRepository")],
            },
            {
                "component": "خط التحليل المشترك (ADR-0005)",
                "responsibility": "منتج الحقائق وأدلتها",
                "interface": "ملفات خام → حقائق مشتركة (لغات/أدلة أطر/"
                             "اعتماديات)",
                "boundaries": "الخدمة المعتمدة get_analysis_service "
                             "(analyze_path/analyze_url) — القراءة والكشف "
                             "لا الإسقاط",
                "declared_dependencies": [],
            },
            {
                "component": "إسقاط المختار فوق الحقائق",
                "responsibility": "إنتاج كل مخرج مطلوب في حامله المثبت "
                                  "(إسقاط المختار المعلن في عقده)",
                "interface": "حقائق مشتركة → حوامل المخرج (أدناه)",
                "boundaries": boundary,
                "declared_dependencies": [
                    s for s in contract.get("skills", [])
                    if s not in ("CloneRepository", "ReadRepository")],
            },
        ],
        "output_fulfillment": carriers,
        "producers": (verified["producers"] if verified else None),
        "data_flow": (verified["data_flow"] if verified else None),
        "note": ("مقترح معماري مشتق من عقد المختار ومتطلبات ما قبل "
                 "الاختيار — أسماء المنتجين فعلية من استدعاءات execute "
                 "المتحقق منها؛ skills المعلنة تبعيات معلنة لا مراحل تنفيذ "
                 "مرتبة مثبتة، والحامل يحدد مكان النتيجة لا منتجها، وحدود "
                 "الحالة خاصة بالبديل مالكها"
                 if verified else
                 "مقترح معماري من عقد المختار ومتطلبات ما قبل الاختيار — "
                 "**قصور مسمى**: مسار منتجي هذه القدرة لم يُتحقق منه فلا "
                 "يُورَّث وصف قدرة أخرى؛ المكونات وحدودها من العقد فقط "
                 "(producers/data_flow = None)"),
    }

    return {
        "requirements": requirements,
        "alternatives": alternatives,
        "risks": risks,
        "cost": cost,
        "architecture_design": architecture_design,
    }


def _engineering_plan_fingerprint(ep: Optional[Dict[str, Any]]) -> tuple:
    """بصمة عميقة محافظة على الأنواع لمحتوى المكونات المعروضة — تعديلها
    بعد العرض يُكشف عند بوابتي الاعتماد والتنفيذ (كالخطة نفسها).

    تُحسب من **الكائن المربوط نفسه** عند كل مقارنة — لا من سجل قرار جديد
    (فلا تُفحص معرّفات وأوقات متجددة عند كل حل). محافظة على الأنواع:
    القائمة والصف تمثيلان مختلفان (JSON كان يطويهما معاً)، ومفاتيح
    القواميس مرتبة استقلالاً عن ترتيب الإدراج، وأي قيمة غير قياسية
    تمثّل بنوعها وrepr لا بطيّها نصاً."""
    if ep is None:
        return ()

    def _canonical(value: Any) -> tuple:
        if isinstance(value, dict):
            return ("dict", tuple(sorted(
                (str(k), _canonical(v)) for k, v in value.items())))
        if isinstance(value, (list, tuple)):
            # القائمة والصف نوعان مختلفان — لا يُطوى أحدهما في الآخر
            return (type(value).__name__,
                    tuple(_canonical(v) for v in value))
        if isinstance(value, (str, int, float, bool, type(None))):
            return (type(value).__name__, value)
        return (type(value).__name__, repr(value))

    return (_canonical(ep),)


@dataclass(frozen=True)
class _ApprovalSnapshot:
    """لقطة مستقلة كاملة للمحتوى الموافق عليه — لا قاموس ``evidence`` القابل
    للتعديل داخل ``ApprovalRequest``. تشمل كائن الاختيار نفسه (هوية التطبيق
    القابل للاستدعاء — اسمان ومعرّف واحد لا يثبتان تطبيقاً واحداً) وبصمة الخطة
    الكاملة وبصمة المعاملات. أي تعديل مع بقاء المعرّف لا يمر."""
    mission_id: str
    capability: str
    plan_fingerprint: tuple
    parameters_fingerprint: str
    selection_identity: tuple
    selection_object: Any = None      # الكائن القابل للاستدعاء الموافق عليه — يُتحقق عند حد الاستدعاء
    #: بصمة مكونات خطة Engineer المعروضة (سجل العمل 0043+0044) — تُفحص
    #: عند الاعتماد والتنفيذ كالخطة نفسها؛ الحقل أُضيف بعد الحقول القائمة
    engineering_plan_fingerprint: tuple = ()


def _parameters_fingerprint(parameters: Any) -> str:
    """بصمة محتوى مستقرة للمعاملات (مرتبة) — لا اعتماد على هوية القاموس."""
    import hashlib
    import json
    payload = json.dumps(parameters or {}, sort_keys=True,
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _ApprovalGuard:
    """حارس مستقل عن حالة طلب الاعتماد القابلة للتعديل:

    - ``SKIPPED`` ليس اعتماداً ولا يجيز التنفيذ؛ والرفض نهائي لا يُقلب حتى لو
      غُيّرت حالة الطلب نفسه لاحقاً إلى ``APPROVED`` (الحارس يحتفظ بحالته
      المستقلة)؛ والاعتماد لا يكون إلا لطلب قائم حالته الحالية ``PENDING``.
    - إجازة التنفيذ **تُستهلك قبل استدعاء العمل** — مرة واحدة؛ والفشل لا
      يعيد تلقائياً بالإجازة نفسها (محاولة واحدة داخل الواجهة).
    - اللقطة تُقارن عند كل استعمال — تعديل الخطة أو المعاملات أو الاختيار مع
      بقاء المعرّف لا يمر.
    """

    def __init__(self) -> None:
        self._bound: Dict[str, _ApprovalSnapshot] = {}
        self._state: Dict[str, str] = {}      # pending/approved/rejected — مستقلة
        self._consumed: set = set()
        self._invalidated: set = set()

    def bind(self, approval_id: str, snapshot: _ApprovalSnapshot) -> None:
        self._bound[approval_id] = snapshot
        self._state[approval_id] = "pending"

    def invalidate(self, approval_id: str) -> None:
        self._invalidated.add(approval_id)

    def approve(self, approval, approval_id: str, approver: str) -> bool:
        self._observe_terminal(approval, approval_id)   # أولاً — قبل بوابات المرحلة
        request = approval.get_request(approval_id)
        if request is None:
            return False
        if self._state.get(approval_id) != "pending":
            return False
        if approval_id in self._invalidated or approval_id in self._consumed:
            return False
        if request.status.value != "pending":
            # مرفوض/منتهي/مقرر مسبقاً لا يُعتمد — **نهائي**: استرجاع الحالة
            # إلى PENDING لاحقاً لا يحيي الطلب
            self._invalidated.add(approval_id)
            return False
        if not approval.approve(approval_id, approver=approver):
            return False
        self._state[approval_id] = "approved"
        return True

    def snapshot(self, approval_id: str):
        """اللقطة المرتبطة — لفحص المحتوى عند الاعتماد أيضاً (لا عند التنفيذ
        وحده)."""
        return self._bound.get(approval_id)

    def observe_content(self, approval_id: str, snapshot_now) -> None:
        """رصد اختلاف المحتوى **قبل أي بوابة مرحلة** — إبطال نهائي لا يحييه
        استرجاع المحتوى لاحقاً. محاولة مبكرة بخطة لم تتغير ليست إبطالاً —
        تُرفض فحسب (لا يُسجل لها إبطال)."""
        bound = self._bound.get(approval_id)
        if bound is not None and snapshot_now != bound:
            self._invalidated.add(approval_id)

    def _observe_terminal(self, approval, approval_id: str) -> None:
        """رصد الحالات النهائية الخارجية (REJECTED/EXPIRED) وتسجيل إبطالها —
        **مشترك قبل أي بوابة مرحلة داخلية** في الاعتماد والتنفيذ معاً: سبب
        الثغرة كان وضع الرصد بعد بوابات المرحلة، فتُرفض مبكراً دون تسجيل
        الانتهاء المرصود. الملاحظة نهائية: استرجاع الحالة لاحقاً لا يحييها."""
        request = approval.get_request(approval_id)
        if request is None:
            return
        status = getattr(request.status, "value", "")
        if status in ("rejected", "expired"):
            self._invalidated.add(approval_id)

    def reject(self, approval, approval_id: str, rejected_by: str,
               reason: str) -> bool:
        approved = approval.reject(approval_id, rejected_by=rejected_by,
                                   reason=reason)
        self._state[approval_id] = "rejected"    # نهائية عند الحارس
        return approved

    def is_invalidated(self, approval_id: str) -> bool:
        """هل سُجل إبطال نهائي لهذا الطلب؟ (لتمييز رسالة الرفض المؤقت عن
        رسالة الإبطال النهائي عند الاستدعاء). إعادة الاستخدام بعد الاستهلاك
        نهائية كذلك."""
        return (approval_id in self._invalidated
                or approval_id in self._consumed)

    def permit_execution(self, approval, approval_id: str,
                         snapshot_now: _ApprovalSnapshot) -> bool:
        """إجازة التنفيذ — تُستهلك قبل الاستدعاء؛ مرة واحدة وبلقطة مطابقة.
        الرفض على وجهين: **مؤقت** (الطلب لم يُعتمد بعد — لا يُسجل إبطالاً
        ويمكن اعتماده لاحقاً) و**نهائي** (إبطال مسجل: اختلاف المحتوى، حالة
        نهائية مرصودة، أو إعادة استخدام بعد الاستهلاك — استرجاع الحالة أو
        المحتوى لاحقاً لا يحييها)."""
        # الملاحظات الموجبة للإبطال (الحالات النهائية واختلاف المحتوى)
        # **قبل بوابات المرحلة** — لا تحجبها بوابة حالة داخلية فتمر
        self._observe_terminal(approval, approval_id)
        self.observe_content(approval_id, snapshot_now)
        if self._state.get(approval_id) != "approved":
            return False
        if approval_id in self._consumed or approval_id in self._invalidated:
            return False
        request = approval.get_request(approval_id)
        if request is None or request.status.value != "approved":
            self._invalidated.add(approval_id)    # نهائي — لا يُحييه استرجاع الحالة
            return False
        if self._bound.get(approval_id) != snapshot_now:
            self._invalidated.add(approval_id)    # نهائي — لا يُحييه استرجاع المحتوى
            return False
        self._consumed.add(approval_id)          # الاستهلاك قبل استدعاء العمل
        return True


# ===============================================================
# الواجهة
# ===============================================================
class IntelligenceInterface:
    """المدخل المعتمد الواحد (ADR-0009). التبعيات قابلة للحقن (اختبارات
    الواجهة تحقن نواة زائفة/محولات زائفة)؛ والافتراضي يبني السلسلة الحية
    الحقيقية بمحولاتها الفعلية."""

    def __init__(self, mission_engine=None, approval=None,
                 capability_resolver=None, kernel_runtime=None):
        if mission_engine is None:
            # السلسلة الحية من **الإقلاع المعتمد** (Bootstrapper) — سجل القدرات
            # والمزوددون الحقيقيان وسلسلة التنفيذ التي بناها فعلاً (سجل العمل
            # 0046): لا سجلات فارغة تُنشأ بجانب الإقلاع، وفشل الإقلاع خطأ
            # معلن لا واجهة "جاهزة" فوق سجل خاوٍ.
            if kernel_runtime is None:
                kernel_runtime = self._boot_live_runtime()
            mission_engine = kernel_runtime.mission_engine
        # المحلل يُستخرج من أنبوب المحرك المستخدم فعلاً — لا محلل افتراضي
        # منفصل عند حقن المحرك وحده (اتساق التحقق مع التنفيذ)
        extracted_resolver, core_wrapper = self._wire_engine(mission_engine)
        if capability_resolver is None:
            capability_resolver = extracted_resolver
        self._mission_engine = mission_engine
        self._kernel_runtime = kernel_runtime   # مالك سجل المهام القائم (rt.missions)
        self._capability_resolver = capability_resolver
        #: خريطة إسناد (سجل العمل 0050): mission_id → {capability, mode} —
        #: إسناد قدرةٍ إلى سجل rt.missions **القائم المالك** (المدة والمهام
        #: منه لا من نسخة موازية)؛ وعند غياب runtime (محركات محقونة) تُسجل
        #: المدة المقيسة من المنفذ داخل الإسناد نفسه (احتياط موثق)
        self._mission_attribution: Dict[str, Dict[str, Any]] = {}
        self._core_wrapper = core_wrapper      # حد التحقق عند الاستدعاء (أو None)
        if approval is None:
            from approval import ApprovalRuntime
            approval = ApprovalRuntime()
        self._approval = approval
        self._guard = _ApprovalGuard()
        self._bound_missions: Dict[str, Any] = {}   # المحتوى الموافق عليه يُنفَّذ (نسخة عميقة)
        self._bound_plans: Dict[str, Any] = {}      # الخطة المعروضة للاعتماد — كائن مشترك
        self._bound_engineering_plans: Dict[str, Any] = {}  # مكونات الخطة المعروضة — كائن مشترك ببصمة عميقة
        self._bound_work: Dict[str, Any] = {}       # العمل المعتمد: (صاحب الدالة، الدالة، المعاملات)
        self._approval_by_mission: Dict[str, str] = {}

    @staticmethod
    def _boot_live_runtime(base_path=None):
        """الإقلاع المعتمد للسلسلة الحية — عبر ``Bootstrapper`` لا سجلات
        موازية. فشل الإقلاع **يُبلَّغ** (استثناء صريح برسائله) ولا يُنشر
        كواجهة جاهزة فوق سجل خاوٍ (سجل العمل 0046)."""
        from agos_runtime import boot
        runtime = boot(base_path)
        if not runtime.ready:
            raise RuntimeError(
                "فشل إقلاع النواة — لا واجهة ذكاء حية فوق إقلاع فاشل: "
                + ("; ".join(runtime.errors) or "سبب غير معروف"))
        return runtime

    @staticmethod
    def _build_default_chain():
        """مُهملة (تبقى للتوافق): السلسلة الافتراضية صارت من الإقلاع الحي
        عبر ``_boot_live_runtime`` — سجل القدرات الحقيقي الذي يحمّله
        ``Bootstrapper`` لا سجل فارغ. المحلل يُستخرج من أنبوب المحرك."""
        runtime = IntelligenceInterface._boot_live_runtime()
        pipeline = getattr(getattr(runtime.mission_engine, "executor", None),
                           "pipeline", None)
        resolver = (getattr(pipeline, "capability_resolver", None)
                    if pipeline else None)
        return runtime.mission_engine, resolver

    @staticmethod
    def _wire_engine(mission_engine):
        """استخراج المحلل وتغليف نواة أنبوب المحرك الفعلي بنواة متحققة —
        التحقق عند حد الاستدعاء لا عند الحل وحده (الأنبوب يعيد الحل داخلياً)."""
        pipeline = getattr(getattr(mission_engine, "executor", None),
                           "pipeline", None)
        if pipeline is None:
            return None, None
        resolver = getattr(pipeline, "capability_resolver", None)
        core = getattr(pipeline, "execution_engine", None)
        if core is None:
            return resolver, None
        if isinstance(core, _VerifyingCore):
            return resolver, core
        wrapper = _VerifyingCore(core)
        pipeline.execution_engine = wrapper      # تغليف مرة واحدة
        return resolver, wrapper

    # ---------- المدخل الموحد ----------
    def run(self, request: IntelligenceRequest) -> IntelligenceResult:
        """تشغيل الطلب — النمط إلزامي ويتحقق قبل أي عمل (لا تحويل صامت)."""
        if not isinstance(request.mode, IntelligenceMode):
            raise ValueError(
                f"نمط ذكاء غير صالح أو غائب: {request.mode!r} — "
                f"الأنماط المعتمدة: instant / engineer / research (ADR-0009)")
        if request.mode is IntelligenceMode.INSTANT:
            return self._run_instant(request)
        if request.mode is IntelligenceMode.ENGINEER:
            return self._run_engineer(request)
        return self._run_research(request)

    # ---------- Instant ----------
    def _run_instant(self, request: IntelligenceRequest) -> IntelligenceResult:
        mission_spec = request.mission
        interpreted = False
        if not mission_spec and request.natural_text:
            # مفسر النية المعلن (سجل العمل 0047): معجم ثنائي + إيفاء مُثبت
            # بالمخرجات — لا تخمين معاملات ولا اختيار بلا تعليل
            from intelligence import intent as intent_module
            interpretation = intent_module.interpret(request.natural_text)
            registered = [c.name for c in
                          self._capability_resolver.capability_registry.list_all()]
            mission_spec, intent_error = intent_module.build_mission(
                interpretation, registered)
            interpreted = True
            if mission_spec is None:
                return IntelligenceResult(
                    mode=IntelligenceMode.INSTANT,
                    status=IntelligenceStatus.FAILED,
                    error=intent_error,
                    gaps=list(INSTANT_GAPS))
        if not mission_spec:
            return IntelligenceResult(
                mode=IntelligenceMode.INSTANT,
                status=IntelligenceStatus.FAILED,
                error="لا مواصفة مهمة — لا مفسر قصد حراً في القائم "
                      "(فجوة مسماة: intent-interpretation)",
                gaps=list(INSTANT_GAPS))
        bound_content = self._stable_content(mission_spec)
        if self._kernel_runtime is not None:
            # المسار الحي المعتمد: يمر عبر ``KernelRuntime.run`` فيُسجَّل في
            # ``rt.missions`` (المالك القائم لسجل التنفيذات) ويقيس المنفذ
            # المدة فعلاً — لا قناة موازية تتجاوز السجل
            outcome = self._kernel_runtime.run(bound_content)
        else:
            outcome = self._mission_engine.run(bound_content)   # parse→validate→plan→execute
        from mission_engine import MissionState
        completed = outcome.state is MissionState.COMPLETED
        gaps = list(INSTANT_GAPS)
        if interpreted:
            # الفجوة أُغلقت للمسار المفسر — لا تُرد فجوة آلية غاب مسبباها
            gaps = [g for g in gaps if g != "intent-interpretation"]
        # إسناد القدرة إلى مهمة سجل rt.missions (المالك) — المدة تُقرأ منه
        self._mission_attribution[outcome.mission_id] = {
            "capability": _mission_field(mission_spec, "capability"),
            "mode": "instant",
            "state": outcome.state.value,
            "parameters": _mission_field(mission_spec, "parameters") or {},
            "duration_ms": outcome.duration_ms,   # احتياط عند غياب runtime
        }
        return IntelligenceResult(
            mode=IntelligenceMode.INSTANT,
            status=IntelligenceStatus.COMPLETED if completed
            else IntelligenceStatus.FAILED,
            mission_id=outcome.mission_id,
            result=outcome.result,
            error=outcome.error,
            decision_records=list(getattr(outcome, "decision_records", None) or []),
            gaps=gaps)

    # ---------- Engineer ----------
    def _run_engineer(self, request: IntelligenceRequest) -> IntelligenceResult:
        mission_spec = request.mission
        interpreted_ctx = None
        if not mission_spec and request.natural_text:
            # مسار الطلب الطبيعي (سجل العمل 0048): المتطلبات قبل الاختيار —
            # تفسير معلن ثم بدائل الإيفاء تقارن عبر دليل القرار القائم
            mission_spec, interpreted_ctx, intent_error = (
                self._interpret_engineer_request(request.natural_text))
            if mission_spec is None:
                return IntelligenceResult(
                    mode=IntelligenceMode.ENGINEER,
                    status=IntelligenceStatus.FAILED,
                    error=intent_error,
                    gaps=list(ENGINEER_GAPS))
        if not mission_spec:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                error="لا مواصفة مهمة — لا مفسر قصد حراً في القائم "
                      "(فجوة مسماة: intent-interpretation)",
                gaps=list(ENGINEER_GAPS))
        bound_content = self._stable_content(mission_spec)
        mission = self._parse_bound(bound_content)
        # التحقق يمنع أي خطة أو اعتماد عند الفشل — كما في السلسلة المتحققة
        from mission_engine import MissionValidator
        validation = MissionValidator().validate(mission)
        if not validation.valid:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                mission_id=mission.id,
                error="فشل التحقق قبل أي خطة أو اعتماد: "
                      + "; ".join(validation.errors),
                gaps=list(ENGINEER_GAPS))
        from mission_engine import MissionPlanner
        plan = MissionPlanner().plan(mission)
        # المفاضلة قبل طلب الاعتماد — هوية الاختيار **وكائنه** تُضمَّنان اللقطة.
        # Engineer بلا عمل معتمد صالح يُرفض قبل إنشاء الاعتماد (لا اعتماد
        # بلا عمل — مفصول عن Instant الذي لا حد اعتماد عليه)
        selection = self._resolve_selection(mission)
        # دليل القرار يستخرج قبل التفرع — فشل الحل لا يُسقط دليلاً موجوداً
        decision_records = [r for r in (getattr(selection, "record", None),)
                          if r is not None]
        selection_ok = (
            selection is not None
            and getattr(selection, "status", None) is not None
            and getattr(selection.status, "value", "") == "success"
            and getattr(selection, "capability", None) is not None)
        if not selection_ok:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                mission_id=mission.id,
                error="لا اختيار صالح للعمل — لا يُنشأ اعتماد بلا عمل معتمد "
                      "(فشل الحل: "
                      + str(getattr(selection, "reason", "لا محلّل")) + ")",
                decision_records=decision_records,   # الدليل مع الفشل
                gaps=list(ENGINEER_GAPS))
        # لا أي استدعاء تنفيذ حتى الاعتماد
        approval_request = self._approval.create_request(
            request_type="intelligence.engineer-plan",
            description=f"خطة Engineer للمهمة: {mission.name}",
            source=self._human_source(), requester="intelligence-interface")
        engineering_plan = _engineering_plan(
            mission, plan, decision_records,
            interpreted=interpreted_ctx,
            measured_executions=(
                self._measured_executions(_mission_field(mission_spec, "capability"))
                if interpreted_ctx is not None else None))
        # فجوات المسار المفسر: ما اشتُق فعلاً يُغلق، وما لا قياس له يبقى مسمى
        gaps = list(ENGINEER_GAPS)
        if interpreted_ctx is not None:
            gaps = [g for g in gaps
                    if g not in interpreted_ctx.get("closed_gaps", [])]
        # المكونات كائن مشترك معروض للاعتماد — كالخطة: تعديلها يُكشف ببصمة
        # عميقة عند بوابتي الاعتماد والتنفيذ (سجل العمل 0044) ولا تمر معدّلة
        self._bound_engineering_plans[approval_request.id] = engineering_plan
        snapshot = self._snapshot(mission, plan, selection, engineering_plan)
        self._guard.bind(approval_request.id, snapshot)
        # الخطة كائن مشترك معروض للاعتماد — تعديلها يظهر عند التنفيذ فيُرفض؛
        # والمحتوى نسخة عميقة معزولة عن تعديل المرسل
        self._bound_plans[approval_request.id] = plan
        self._bound_missions[approval_request.id] = bound_content
        import copy as _copy
        approved_function = getattr(getattr(selection, "capability", None),
                                     "execute", None)
        self._bound_work[approval_request.id] = (
            getattr(selection, "capability", None),       # صاحب الدالة
            getattr(approved_function, "__func__",
                    approved_function),                   # الدالة نفسها
            # المعاملات الموافق عليها: **نسخة عميقة مستقلة** — لا تشارك
            # المحلل القاموسَ فيصيب تعديله طرفي المقارنة معاً
            _copy.deepcopy(getattr(mission, "parameters", None) or {}),
        )
        previous = self._approval_by_mission.get(mission.id)
        if previous and previous != approval_request.id:
            self._guard.invalidate(previous)     # خطة جديدة لنفس المهمة تبطل اعتمادها السابق
        self._approval_by_mission[mission.id] = approval_request.id
        return IntelligenceResult(
            mode=IntelligenceMode.ENGINEER,
            status=IntelligenceStatus.AWAITING_APPROVAL,
            mission_id=mission.id,
            plan=plan,
            approval_id=approval_request.id,
            decision_records=decision_records,
            engineering_plan=engineering_plan,
            gaps=gaps)

    def _interpret_engineer_request(self, natural_text: str):
        """الطلب الطبيعي في Engineer: متطلبات قبل الاختيار، وبدائل إيفاء
        تقارن عبر دليل القرار القائم (سياسته الحية) — لا محرك ترتيب موازٍ.

        الترتيب الصريح: نص المستخدم ← مفاهيم/مصادر ← بدائل الإيفاء ←
        مقارنة دليل القرار ← الفائز — لا اشتقاق متطلبات من قدرة مختارة."""
        from intelligence import intent as intent_module
        interpretation = intent_module.interpret(natural_text)
        if interpretation.verbal_negation:
            return None, None, ("نفي فعلي (لا/ليس) نطاقه الجملة — لا آلية "
                                "محدودة تحسم ما نُفي بالضبط، فالطلب لا "
                                "يُنفَّذ (غموض مسمّى: intent-interpretation). "
                                "المنفيات قيود تُعرض للمعتمِد لا متطلبات "
                                "تُحذف صامتة.")
        if interpretation.interrogative:
            return None, None, ("طلب استفهامي — سؤال لا أمر تنفيذ؛ يُوجَّه "
                                "للبحث لا للتنفيذ (فجوة مسماة: "
                                "intent-interpretation)")
        if not interpretation.required_concepts:
            return None, None, ("لا مفاهيم مطلوبة مفهومة من الطلب — المعجم "
                                "المعلن لم يطابق شيئاً (فجوة مسماة: "
                                "intent-interpretation)")
        registered = [c.name for c in
                      self._capability_resolver.capability_registry.list_all()]
        alternatives, unfulfilled = intent_module.ranked_candidates(
            interpretation, registered)
        if unfulfilled:
            return None, None, ("لا قدرة مسجلة يحمل مخرجها المفهوم المطلوب: "
                                + ", ".join(unfulfilled)
                                + " (فجوة مسماة: intent-interpretation)")
        if not alternatives:
            return None, None, ("لا قدرة مسجلة تحقق المفاهيم معاً: "
                                + ", ".join(interpretation.required_concepts)
                                + " (فجوة مسماة: intent-interpretation)")
        required_skills = intent_module.derived_skills(interpretation)
        comparison = self._compare_alternatives(alternatives, required_skills)
        selected = getattr(comparison, "selected", None)
        if getattr(comparison, "status", None) != "selected" or not selected:
            return None, None, ("تعذر اختيار بين البدائل في دليل القرار — "
                                "لا اعتماد بلا عمل صالح (" 
                                + str(getattr(comparison, "status", "")) + ")")
        # القيد المنفي مُلزم (سجل العمل 0051): لا اختيار صامت يتجاهله —
        # إن كان المختار يحمل المنفي في مخرجه فلا إثبات لاحترامه فلا تنفيذ
        violated = [c for c in interpretation.negated_concepts
                   if selected in intent_module.FULFILLMENT.get(c, {})]
        if violated:
            return None, None, ("القيد المنفي (" + ", ".join(violated)
                                + ") لا يمكن إثبات احترامه: المختار ("
                                + selected + ") يحمله في مخرجه وعقده لا "
                                "يعلّم تعطيله — لا تنفيذ ولا تجاهل صامت "
                                "(فجوة مسماة: intent-interpretation)")
        if selected in intent_module.NEEDS_REPOSITORY_SOURCE \
                and "url" not in interpretation.artifacts:
            return None, None, ("المدخل المطلوب غائب: " + selected
                                + " يحتاج مصدر مستودع (رابط أو مسار) ولم "
                                  "يُذكر في الطلب (فجوة مسماة: "
                                  "intent-interpretation)")
        mission_spec = {
            "name": "نية: " + " + ".join(sorted(
                interpretation.required_concepts)),
            "description": "مهمة مبنية من طلب طبيعي (مفسر النية المعلن)",
            "capability": selected,
            "parameters": dict(interpretation.artifacts),
        }
        # فجوات تُغلق بما اشتُق فعلاً — والتكلفة المقيسة تُغلق عند وجود قياس
        closed = ["intent-interpretation",
                 "engineering-plan-requirements-analysis",
                 "engineering-plan-design-alternatives",
                 "engineering-plan-risks"]
        # فجوة المعمارية تُغلق فقط لمختار متحقق من مسار منتجيه (0053) —
        # ما لم يُتحقق لا يُورَّث وصف غيره فالفجوة تبقى مسماة
        if selected in _VERIFIED_PRODUCER_PATHS:
            closed.append("engineering-plan-architecture")
        # مجموعة المقارنة نفسها (سجل العمل 0052): وضع + مدخل الطلب — تنفيذ
        # مدخل آخر لا يغلق فجوة هذا الطلب
        request_parameters = dict(interpretation.artifacts)
        measured = [e for e in self._measured_executions(selected)
                   if e["state"] == "completed" and e.get("mode") == "engineer"
                   and dict(e.get("parameters") or {}) == request_parameters]
        if measured:
            closed.append("engineering-plan-cost-estimate")
        # عقود البدائل من السجل الحي — تصميم كل بديل ومهاراته المعلنة
        registry = self._capability_resolver.capability_registry
        registered_objects = {c.name: c for c in registry.list_all()}
        contracts = {
            name: {"description": str(getattr(registered_objects[name],
                                              "description", "") or ""),
                   "skills": list(getattr(registered_objects[name],
                                          "skills", []) or [])}
            for name in alternatives if name in registered_objects}
        interpreted_ctx = {
            "natural_text": natural_text,
            "interpretation": interpretation,
            "alternatives": list(alternatives),
            "required_skills": list(required_skills),
            "contracts": contracts,
            "comparison": comparison,
            "selected": selected,
            "closed_gaps": closed,
        }
        return mission_spec, interpreted_ctx, None

    def _compare_alternatives(self, alternative_names: List[str],
                              required_skills: List[str]):
        """مقارنة بدائل التصميم عبر **دليل القرار القائم** بسياسة بدائل
        معلنة (سجل العمل 0051 — تصحيح 0050): كل المرشحين مُثبت إيفاؤهم
        بحوامل المخرجات الفعلية فدرجاتهم متساوية (تعادل إيفاء حقيقي) —
        لا معيار علاقة مهارات هنا ولا أفضلية من عدد التبعيات؛ وقاعدة
        الاختيار معلنة (ترتيب التسجيل المستقر) والمعتمِد يرى التصميمين
        ويميّز أو يرفض. لا محرك ترتيب موازٍ."""
        import uuid as _uuid
        from decision_pipeline import (DECISION_CORE, DecisionCandidate,
                                       DecisionPolicy, DecisionRequest)
        from decision_pipeline import _utc_now_iso
        policy = DecisionPolicy(
            policy_id="design-alternatives-fulfillment-tie",
            version="1.0.0",
            kind="capability",
            weights={"skill": 1.0, "priority_weight": 0.0},
            rules={
                "capability_scoring": "jaccard-exact-override",
                "tie_break": "stable-registration-order",
                "note": "تعادل إيفاء حقيقي: كل المرشحين مُثبت إيفاؤهم "
                        "بحوامل المخرجات — الدرجات متساوية وقاعدة الاختيار "
                        "معلنة (ترتيب التسجيل)، لا أفضلية تصميمية من عدد "
                        "التبعيات المطلوبة",
            })
        registry = self._capability_resolver.capability_registry
        registered = {c.name: c for c in registry.list_all()}
        # الترتيب بفهرس التسجيل الفعلي (مررها مرتبة كذلك)
        registration_index = {c.name: i for i, c in enumerate(
            registry.list_all())}
        ordered = sorted(alternative_names,
                        key=lambda n: registration_index.get(n, 10**9))
        candidates = [DecisionCandidate(
            name=name,
            skills_query=(lambda c=registered[name]: getattr(c, "skills", [])),
            priority_query=(lambda c=registered[name]: getattr(c, "priority", 1.0)),
            ref=registered[name])
            for name in ordered if name in registered]
        # لا مهارات مطلوبة في الطلب: الإيفاء مثبت بالحوامل لا بالدرجات —
        # فالتعادل حقيقي لا مصنوع
        return DECISION_CORE.evaluate(
            DecisionRequest(kind="capability", requested_name="",
                            required_skills=[], constraints=[]),
            candidates, policy,
            decision_id=f"cap-{_uuid.uuid4()}", timestamp=_utc_now_iso())

    def approve(self, approval_id: str, approver: str) -> IntelligenceResult:
        """اعتماد صريح — حالة **APPROVED** فقط، لا تنفيذ (التنفيذ بإجازة
        مستقلة تُستهلك مرة)."""
        bound_content = self._bound_missions.get(approval_id)
        if bound_content is None:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                error=f"لا خطة مربوطة بهذا الاعتماد: {approval_id!r}")
        # فحص المحتوى المعروض **عند الاعتماد أيضاً** — لا اعتماد لخطة معدلة،
        # واسترجاعها لا يحيي الطلب: التعديل يحتاج طلب اعتماد جديداً (ADR-0009)
        mission = self._parse_bound(bound_content)
        plan = self._bound_plans[approval_id]
        selection_now = self._resolve_selection(mission)
        bound_snapshot = self._guard.snapshot(approval_id)
        if bound_snapshot is not None and self._snapshot(
                mission, plan, selection_now,
                self._bound_engineering_plans.get(approval_id)) != bound_snapshot:
            self._guard.invalidate(approval_id)     # نهائي
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                mission_id=mission.id,
                approval_id=approval_id,
                error="المحتوى المعروض تغيّر عن لقطة إنشاء الطلب (الخطة/"
                      "المعاملات/الاختيار) — لا يُعتمد؛ التعديل يحتاج طلب "
                      "اعتماد جديداً، واسترجاع المحتوى لا يحيي الطلب",
                gaps=list(ENGINEER_GAPS))
        if not self._guard.approve(self._approval, approval_id, approver):
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                error="رفض الاعتماد: الطلب غير قائم أو غير معلق أو حُسم سابقاً "
                      "(SKIPPED/REJECTED لا يعتمدان — ADR-0009)")
        return IntelligenceResult(
            mode=IntelligenceMode.ENGINEER,
            status=IntelligenceStatus.APPROVED,
            mission_id=self._parse_bound(
                self._bound_missions[approval_id]).id,
            approval_id=approval_id,
            gaps=list(ENGINEER_GAPS))

    def reject(self, approval_id: str, rejected_by: str,
               reason: str) -> IntelligenceResult:
        """رفض صريح — نهائي عند الحارس، ولا تنفيذ."""
        self._guard.reject(self._approval, approval_id, rejected_by, reason)
        return IntelligenceResult(
            mode=IntelligenceMode.ENGINEER,
            status=IntelligenceStatus.REJECTED,
            approval_id=approval_id,
            error=f"رُفض الاعتماد: {reason}",
            gaps=list(ENGINEER_GAPS))

    def execute_approved(self, approval_id: str) -> IntelligenceResult:
        """تنفيذ العمل **الموافق عليه** — الإجازة تُستهلك قبل الاستدعاء، مرة
        واحدة، وبعد التحقق أن المحتوى الحالي يطابق لقطة الاعتماد (الخطة
        والمعاملات والاختيار) وإلا فشل صريح."""
        bound_content = self._bound_missions.get(approval_id)
        if bound_content is None:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                error=f"لا خطة مربوطة بهذا الاعتماد: {approval_id!r}")
        if self._core_wrapper is None:
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                error="لا يمكن التحقق من الاختيار عند حد الاستدعاء (لا نواة "
                      "قابلة للتغليف في المحرك) — يُرفض التنفيذ بلا حد الاعتراض")
        mission = self._parse_bound(bound_content)
        # الخطة المرتبطة نفسها (كائن مشترك) — تعديلها يظهر هنا فيُرفض
        plan = self._bound_plans[approval_id]
        selection_now = self._resolve_selection(mission)
        snapshot_now = self._snapshot(
            mission, plan, selection_now,
            self._bound_engineering_plans.get(approval_id))
        if not self._guard.permit_execution(self._approval, approval_id,
                                            snapshot_now):
            if self._guard.is_invalidated(approval_id):
                error = ("إجازة التنفيذ مرفوضة نهائياً: سُجل إبطال (اختلاف "
                         "المحتوى، حالة نهائية، أو إعادة استخدام بعد "
                         "الاستهلاك) — استرجاع الحالة أو المحتوى لا يحييها "
                         "(ADR-0009)")
            else:
                error = ("الطلب غير معتمد بعد — الإجازة لم تُمنح. محاولة "
                         "مبكرة لا تُبطل الطلب: يمكن اعتماده ثم تنفيذه "
                         "لاحقاً (ADR-0009)")
            return IntelligenceResult(
                mode=IntelligenceMode.ENGINEER,
                status=IntelligenceStatus.FAILED,
                mission_id=mission.id,
                approval_id=approval_id,
                error=error,
                gaps=list(ENGINEER_GAPS))
        # حد الاستدعاء: العمل الموافق عليه كاملاً (صاحب الدالة والدالة نفسها
        # والمعاملات) وحده يمر إلى النواة — تغيّر الاختيار أو الدالة أو
        # المعاملات داخل الأنبوب يُرفض هناك قبل أي عمل
        wrapper = self._core_wrapper
        wrapper.expected = self._bound_work.get(approval_id)
        try:
            # المسار الحي المعتمد (سجل العمل 0050): المرور عبر
            # KernelRuntime.run فيُسجَّل في rt.missions (المالك القائم
            # لسجل التنفيذات) — والحارس محفوظ (المحرك المسوَّر نفسه)
            if self._kernel_runtime is not None:
                outcome = self._kernel_runtime.run(bound_content)
            else:
                outcome = self._mission_engine.run(bound_content)  # السلسلة كاملة
        finally:
            wrapper.expected = None
        from mission_engine import MissionState
        completed = outcome.state is MissionState.COMPLETED
        # إسناد القدرة إلى مهمة سجل rt.missions (المالك) — المدة تُقرأ منه
        parameters = getattr(mission, "parameters", None) or {}
        version = ""
        registry = getattr(self._capability_resolver, "capability_registry", None)
        if registry is not None:
            try:
                cap_obj = registry.get(
                    str(getattr(mission, "capability", "") or ""))
            except (TypeError, KeyError, ValueError):
                cap_obj = None
            if cap_obj is not None:
                version = str(getattr(cap_obj, "version", "") or "")
        self._mission_attribution[outcome.mission_id] = {
            "capability": str(getattr(mission, "capability", "") or ""),
            "mode": "engineer",
            "state": outcome.state.value,
            "parameters": parameters,
            "capability_version": version,
            "duration_ms": outcome.duration_ms,   # احتياط عند غياب runtime
        }
        return IntelligenceResult(
            mode=IntelligenceMode.ENGINEER,
            status=IntelligenceStatus.COMPLETED if completed
            else IntelligenceStatus.FAILED,
            mission_id=outcome.mission_id,
            result=outcome.result,
            error=outcome.error,
            decision_records=list(getattr(outcome, "decision_records", None) or []),
            gaps=list(ENGINEER_GAPS))

    # ---------- Research ----------
    #: فئات الحقائق المقابلة للمفاهيم (جدول معلن — السؤال يقود الجمع)
    _CONCEPT_FACT_CATEGORIES = {
        "frameworks": "frameworks",
        "languages": "languages",
        "repository-analysis": None,   # فعل عام — لا فئة واحدة
    }

    def _run_research(self, request: IntelligenceRequest) -> IntelligenceResult:
        """Research — المقارنة في دليل القرار نفسه (سياسة واحدة) لا محرك
        ترتيب موازٍ، والفجوات مسماة، والأدلة من الخط المعتمد (ADR-0005).

        البحث متعدد المصادر (سجل العمل 0049): ``evidence_paths`` — إثبات
        **لكل مصدر لكل مرشح** (لا اتحاد)؛ التعارض ادعاءان متنافسان على
        الموضوع والسياق نفسه؛ وغياب دليل مصدر مسمّى (لا نتيجة مزعومة)؛
        والسؤال يقود جمع الأدلة (مفاهيمه المفسرة ← فئات الحقائق بجدول
        معلن — تغيير السؤال يغيّر الأدلة المجمعة، مختبر)."""
        if request.evidence_paths:
            return self._run_research_multi_source(request)
        question_interpretation, fact_categories = self._question_focus(
            request.question)
        if not request.evidence_path:
            return IntelligenceResult(
                mode=IntelligenceMode.RESEARCH,
                status=IntelligenceStatus.RECOMMENDATION_UNAVAILABLE,
                error="لا مصدر أدلة (مسار مستودع) — لا جمع أدلة بلا مصدر",
                gaps=list(RESEARCH_GAPS) + ["no-evidence-source"])
        # أدلة حقيقية من الخط المعتمد (ADR-0005) — لا نتائج بحث مزعومة
        shared = self._analyze(request.evidence_path)
        facts = _evidence_facts(shared)
        evidence_snapshot = {
            "evidence_path": request.evidence_path,
            "question": request.question or "",
            "question_concepts": (
                question_interpretation.required_concepts
                if question_interpretation else []),
            "fact_categories_gathered": fact_categories,
            "detected": self._gathered_facts(facts, fact_categories),
            # حزمة المقارنة كما استخدمتها المقارنة فعلاً (بفئات السؤال إن وجدت)
            "detected_stack": list(_detected_stack_names(
                shared, fact_categories or None)),
        }
        if not request.candidates:
            return IntelligenceResult(
                mode=IntelligenceMode.RESEARCH,
                status=IntelligenceStatus.RECOMMENDATION_UNAVAILABLE,
                error="لا مرشحين للمقارنة — لا توصية بلا مرشحين",
                evidence_snapshot=evidence_snapshot,
                gaps=list(RESEARCH_GAPS) + ["no-candidates"])
        # السؤال يقود المقارنة: الحزمة بفئات سؤال البحث (سجل العمل 0050)
        comparison = compare_candidates(
            request.candidates, shared, fact_categories=fact_categories or None)
        if comparison.best is None:
            # تقاطع الجميع صفراً — المقارنة محفوظة، ولا توصية بلا مواءمة
            return IntelligenceResult(
                mode=IntelligenceMode.RESEARCH,
                status=IntelligenceStatus.RECOMMENDATION_UNAVAILABLE,
                error="no-relevant-evidence: لا مواءمة مثبتة لأي مرشح مع "
                      "حزمة المستودع المكتشفة",
                comparison=comparison,
                evidence_snapshot=evidence_snapshot,
                gaps=list(RESEARCH_GAPS) + ["no-relevant-evidence"])
        return IntelligenceResult(
            mode=IntelligenceMode.RESEARCH,
            status=IntelligenceStatus.COMPLETED,
            comparison=comparison,
            evidence_snapshot=evidence_snapshot,
            gaps=list(RESEARCH_GAPS))

    def _run_research_multi_source(
            self, request: IntelligenceRequest) -> IntelligenceResult:
        """بحث متعدد المصادر — إثبات لكل مصدر لكل مرشح (لا اتحاد): كل مصدر
        يُحلّل ويُقارن على حدة؛ والتعارض ادعاءان متنافسان على الموضوع
        والسياق نفسه (عرض تبادلي)؛ وغياب دليل مصدر مسمّى لا نتيجة مزعومة؛
        ولا توصية مدمجة — اتفاق المصادر ملاحظة معروضة لا دمج أدلة."""
        question_interpretation, fact_categories = self._question_focus(
            request.question)
        sources: List[Dict[str, Any]] = []
        failed_sources: List[str] = []
        claims_by_source: Dict[Any, Dict[str, Dict[str, Any]]] = {}
        for claim in (request.source_claims or []):
            sid = claim.get("source_id")
            if sid is None:      # بلا معرّف مصدر: أوّل مصدر بمساره
                try:
                    sid = request.evidence_paths.index(
                        str(claim.get("path", "")))
                except ValueError:
                    continue       # دعوى بلا مصدر — لا تُطابق صامتاً
            claims_by_source.setdefault(sid, {})[
                str(claim.get("property", ""))] = {
                "value": bool(claim.get("value", False)),
                "evidence": str(claim.get("evidence", ""))}
        for source_id, path in enumerate(request.evidence_paths):
            entry: Dict[str, Any] = {"path": path, "source_id": source_id}
            entry["explicit_claims"] = claims_by_source.get(source_id, {})
            try:
                shared = self._analyze(path)
                digest, reliable = _analysis_content_digest(shared)
                entry["content_digest"] = digest
                entry["content_identity_reliable"] = reliable
                facts = _evidence_facts(shared)
                entry["detected"] = self._gathered_facts(facts, fact_categories)
                entry["detected_stack"] = list(_detected_stack_names(
                    shared, fact_categories or None))
                if request.candidates:
                    entry["comparison"] = compare_candidates(
                        request.candidates, shared,
                        fact_categories=fact_categories or None)
                else:
                    entry["comparison"] = None
                    entry["error"] = "لا مرشحين للمقارنة لهذا المصدر"
            except Exception as exc:                               # noqa: BLE001
                entry["error"] = f"تعذر تحليل المصدر: {exc}"
                failed_sources.append(path)
            sources.append(entry)
        cross = self._cross_source_view(sources)
        snapshot = {
            "sources": sources,
            "cross_source": cross,
            "question": request.question or "",
            "question_concepts": (
                question_interpretation.required_concepts
                if question_interpretation else []),
            "fact_categories_gathered": fact_categories,
        }
        if failed_sources:
            return IntelligenceResult(
                mode=IntelligenceMode.RESEARCH,
                status=IntelligenceStatus.FAILED,
                error="غياب دليل مصدر مسمّى (لا نتيجة مزعومة): "
                      + ", ".join(failed_sources),
                evidence_snapshot=snapshot,
                gaps=list(RESEARCH_GAPS))
        bests = [s["comparison"].best for s in sources
                 if s.get("comparison") is not None]
        # لا توصية مدمجة: اتفاق المصادر على الأفضل ملاحظة تُعرض؛ والخلط
        # أو غياب مواءمة مصدر يجعلها غير متاحة
        agreed = (len(bests) == len(sources) and len(sources) > 0
                  and all(b is not None for b in bests)
                  and len({b.candidate_id for b in bests}) == 1)
        status = (IntelligenceStatus.COMPLETED if agreed
                  else IntelligenceStatus.RECOMMENDATION_UNAVAILABLE)
        return IntelligenceResult(
            mode=IntelligenceMode.RESEARCH,
            status=status,
            evidence_snapshot=snapshot,
            gaps=list(RESEARCH_GAPS))

    def _measured_executions(self, capability: str) -> List[Dict[str, Any]]:
        """التنفيذات المقيسة لقدرة — **من سجل rt.missions القائم (المالك)**
        بإسناد المعرّف (خريطة الإسناد)، لا نسخة موازية؛ وعند غياب runtime
        (محرك محقون) يُقرأ احتياط الإسناد الموثق نفسه. المدة قياس المنفذ."""
        records: List[Dict[str, Any]] = []
        if self._kernel_runtime is not None:
            for m in self._kernel_runtime.missions:
                attribution = self._mission_attribution.get(m.mission_id)
                if not attribution:
                    continue
                records.append({
                    "capability": attribution["capability"],
                    "mode": attribution["mode"],
                    "state": m.state.value,
                    "duration_ms": m.duration_ms,
                    "parameters": attribution.get("parameters", {}),
                    "capability_version": attribution.get("capability_version", ""),
                    "source": "rt.missions",
                })
        else:
            for mission_id, attribution in self._mission_attribution.items():
                records.append({
                    "capability": attribution["capability"],
                    "mode": attribution["mode"],
                    "state": attribution["state"],
                    "duration_ms": attribution.get("duration_ms", 0),
                    "parameters": attribution.get("parameters", {}),
                    "capability_version": attribution.get("capability_version", ""),
                    "source": "attribution-fallback",
                })
        return [r for r in records if r["capability"] == capability]

    def _question_focus(self, question: Optional[str]):
        """تركيز السؤال: مفاهيمه بالمفسر المعلن ← فئات الحقائق المجمعة
        (جدول معلن) — السؤال يقود جمع الأدلة؛ بلا سؤال أو بلا فئة معروفة
        تبقى الأدلة كاملة (موسومة لا مختصرة صامتة)."""
        if not question:
            return None, []
        from intelligence import intent as intent_module
        interpretation = intent_module.interpret(question)
        categories: List[str] = []
        for concept in interpretation.required_concepts:
            category = self._CONCEPT_FACT_CATEGORIES.get(concept)
            if category and category not in categories:
                categories.append(category)
        return interpretation, categories

    def _gathered_facts(self, facts: Dict[str, Any],
                        fact_categories: List[str]) -> Dict[str, Any]:
        """الحقائق المجمعة وفق فئات سؤال البحث — لا قصّ صامت: ما استُبعد
        يُسمّى؛ وبلا فئات تُرد الحقائق كاملة كما هي (توافق الشكل القائم)."""
        if not fact_categories:
            return dict(facts)   # الأدلة كاملة — السؤال غائب أو بلا فئة معروفة
        gathered = {c: facts.get(c) for c in fact_categories if c in facts}
        excluded = [c for c in facts if c not in fact_categories]
        return {"categories": gathered,
                "excluded_by_question": excluded,
                "note": "جُمعت فئات سؤال البحث فقط — الاستبعاد مسمّى"}

    def _cross_source_view(self, sources: List[Dict[str, Any]]
                           ) -> Dict[str, Any]:
        """عرض تبادلي بين المصادر — لا اتحاد: الاتفاق ملاحظة معروضة،
        واختلاف المستودعات اختلاف موثق لا تعارض. التعارض الحقيقي يتطلب
        الموضوع والسياق نفسيهما (المستودع والمراجعة نفسها) وادعاءين
        متنافسين مسندين — وما لا نملكه هنا (مصادر مختلفة المستودعات) لا
        يُصنع تعارضاً؛ وغياب الدليل في مصدر ليس إثبات عدم الوجود."""
        agreements: List[Dict[str, Any]] = []
        differences: List[Dict[str, Any]] = []
        ok_sources = [s for s in sources if "detected_stack" in s]
        if not ok_sources:
            return {"agreements": agreements, "differences": differences,
                    "conflicts": [],
                    "note": "لا مصادر محلّلة للعرض التبادلي"}
        all_names: Dict[str, List[str]] = {}
        for s in ok_sources:
            for name in s["detected_stack"]:
                all_names.setdefault(name, []).append(s["path"])
        for name, paths in all_names.items():
            if len(paths) == len(ok_sources):
                agreements.append({"subject": f"stack: {name}",
                                   "claim": "مكتشف في كل المصادر"})
            else:
                differences.append({
                    "subject": f"stack: {name}",
                    "observations": [
                        {"source": p, "observation": "مكتشف" if p in paths
                         else "غير مكتشف — غياب دليل لا إثبات عدم"}
                        for p in [s["path"] for s in ok_sources]]})
        # التعارض (سجل العمل 0052 — تصحيح 0051): تساوي المسار وحده لا يثبت
        # تساوي المراجعة والسياق، و«غير مكتشف» غياب دليل لا ادعاء —
        # فالتعارض يشترط: الموضوع نفسه (المسار) **وهوية محتوى متطابقة**
        # (فهرس الملفات: مسار+حجم+هاش — سياق متوافق مثبت) + نتيجتا كشف
        # مختلفتان عن المدخل نفسه = ادعاءان متنافسان (المدخل المطابق لا
        # ينتج نتيجتين من الكاشف نفسه إلا بخطأ أحدهما) — كل ادعاء بهوية
        # مصدره (source_id) لا بتكرار المسار؛ واختلاف هوية المحتوى
        # (مراجعة تغيّرت) اختلاف لا تعارض؛ وغياب الكشف لا يولّد تعارضاً
        # التعارض (سجل العمل 0053 — تصحيح 0052): قوائم الكشف ليست ادعاءات
        # حصرية — Flask في كشف وDjango في آخر قد يصحان معاً (لا عقد يقول
        # إن القائمة شاملة وحصرية) — فاختلاف القوائم اختلاف موثق دائماً
        # ولو تطابقت هوية المحتوى. التعارض الوحيد المثبت: **ادعاءان
        # صريحان متنافيان** عن الخاصية نفسها (إثبات وجود مقابل إنكار صريح
        # مسند — لا مجرد عدم اكتشاف) في سياق متوافق مثبت؛ وهوية المحتوى
        # لا تُدَّعى موثوقة إلا بتجزئة فعلية للمحتوى (سياستنا لا تهشّ —
        # فالسياق غير قابل للإثبات حالياً ويسمّى كذلك)
        conflicts = []
        # التعارض (سجل العمل 0054 — تصحيح 0053): الدعوى الصريحة تحمل هويتها
        # (المسار والخاصية والقيمة والدليل) — دعويان متنافيتان عن الخاصية
        # نفسها لمسار واحد = تعارض، بغض النظر عن الكشف التحليلي؛ والمصدر
        # الصامت عن الخاصية لا يُسقط تعارض المدّعيين (لا يشارك في المقارنة
        # أصلاً)؛ والدعاوى تصل من مدخل الواجهة (source_claims)
        claims_by_key: Dict[tuple, List[Dict[str, Any]]] = {}
        for src in ok_sources:
            for prop, claim in (src.get("explicit_claims") or {}).items():
                claims_by_key.setdefault((src["path"], prop), []).append({
                    "src": src, "value": bool(claim.get("value")),
                    "evidence": str(claim.get("evidence", ""))})
        for (path, prop), entries in sorted(claims_by_key.items()):
            if len(entries) < 2:
                continue
            values = {e["value"] for e in entries}
            if len(values) < 2:
                continue          # لا تنافي — كل المدّعين متفقون
            conflicts.append({
                "subject": f"explicit-claim: {prop}",
                "context": f"المسار نفسه ({path}) — الخاصية نفسها",
                "claims": [
                    {"source_id": e["src"].get("source_id"),
                     "path": e["src"]["path"],
                     "claim": "أثبت" if e["value"] else "أنكر صراحةً",
                     "evidence": e["evidence"]}
                    for e in entries],
                "note": "دعويان صريحتان متنافيتان عن الخاصية نفسها "
                        "لمسار واحد — يُعرضان بقيمة كل دعوى ودليلها "
                        "وهوية مصدرها للفصل، لا يُدجان ولا يُحسمان هنا؛ "
                        "والمصدر الصامت عن الخاصية لا يُسقط تعارضهما",
            })
        return {
            "agreements": agreements,
            "differences": differences,
            "conflicts": conflicts,
            "note": "اختلاف المستودعات وقوائم الكشف اختلاف موثق لا "
                    "تعارض — القوائم ليست ادعاءات حصرية (عنصران قد يصحان "
                    "معاً)؛ التعارض الوحيد المثبت: دعويان صريحتان متنافيتان "
                    "عن الخاصية نفسها لمسار واحد، تصلان من مدخل الواجهة "
                    "(source_claims) بقيمة كل دعوى ودليلها؛ والتحليل "
                    "الحالي لا ينتج ادعاءات صريحة أصلاً (لا إثبات ولا إنكار "
                    "مسند) فلا تعارض يُستنتج من الكشف — والتحليل لا يهشّ "
                    "المحتوى (hash_predicate=None) فتوافق سياقه غير قابل "
                    "للإثبات (بيانات وصفية بلا تجزئة) ويسمّى كذلك",
        }

    def _analyze(self, path: str) -> Any:
        """خط ADR-0005 — التحليل المشترك عبر الخدمة المعتمدة (بلا كاشف موازٍ)."""
        from capabilities.analysis_service import ScanPolicy, get_analysis_service
        return get_analysis_service().analyze_path(path, policy=ScanPolicy())

    @staticmethod
    def _stable_content(mission_spec: Any) -> Any:
        """محتوى مستقر قابل للربط: **نسخة عميقة** (المعاملات المتداخلة معزولة
        عن تعديل مقدم الطلب) بمعرّف مثبت — والمواصفة قاموس **أو كائن Mission**
        (عقد ADR-0009؛ المحلل يعيد الكائن نفسه). المحتوى الموافق عليه هو الذي
        يُنفَّذ."""
        import copy
        from mission_engine import MissionParser
        if isinstance(mission_spec, dict):
            mission_dict = copy.deepcopy(mission_spec)
            mission = MissionParser.parse(mission_dict)
            mission_dict["id"] = mission.id
            return mission_dict
        return copy.deepcopy(mission_spec)      # كائن Mission معزول عن المرسل

    @staticmethod
    def _parse_bound(bound_content: Any):
        """تحليل المحتوى المرتبط (قاموس أو Mission) — الكائن نفسه يعاد."""
        from mission_engine import MissionParser
        return MissionParser.parse(bound_content)

    def _resolve_selection(self, mission):
        """حل القدرة كما في المسار الحي — دليل القرار يرافقه (ADR-0006)."""
        from context import ExecutionContext
        return self._capability_resolver.resolve(mission, ExecutionContext(mission=mission))

    @staticmethod
    def _snapshot(mission, plan, selection, engineering_plan=None) -> _ApprovalSnapshot:
        """لقطة الاعتماد: الخطة + العمل + المعاملات + **هوية الاختيار المحلول**
        + بصمة مكونات الخطة المعروضة (سجل العمل 0044)."""
        identity = ()
        if selection is not None:
            identity = (str(getattr(selection, "capability_name", "") or ""),
                        str(getattr(selection, "manifest_id", "") or ""))
        return _ApprovalSnapshot(
            mission_id=str(mission.id),
            capability=str(getattr(mission, "capability", "") or ""),
            plan_fingerprint=_plan_fingerprint(plan),
            parameters_fingerprint=_parameters_fingerprint(
                getattr(mission, "parameters", None)),
            selection_identity=identity,
            selection_object=getattr(selection, "capability", None),
            engineering_plan_fingerprint=_engineering_plan_fingerprint(
                engineering_plan))

    @staticmethod
    def _human_source():
        from approval import ApprovalSource
        return ApprovalSource.HUMAN
