"""Decision Pipeline — the unified decision line (R-W1-004, ADR-0006).

All decision paths delegate here: the live resolvers (``resolvers/``), the old
``decision/`` engine, and manual recording (``cognitive.decision``) all produce
their selections through :class:`DecisionCore` — one evaluation core with
declared policies and a full evidence record. No hidden constants, no
unevaluated "constraints satisfied" claims, no zero-support candidates
silently selected. Old interfaces keep their signatures and output types
(G2) — they are projections over this line.

The evidence contract (:class:`DecisionRecord`): identity, the request
actually used, every candidate considered with the values each rule used,
exclusions with named reasons, the declared policy (identity+version),
the chosen candidate with ranked alternatives and the tie-break rule
applied, named missing information, evaluation errors, and an explicit
status when no candidate qualifies (UNDECIDABLE/NO_MATCH — not a silent
fallback to an unrelated candidate).
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class DecisionStatus(Enum):
    """Decision status."""
    PENDING = "pending"
    VALIDATING = "validating"
    COLLECTING = "collecting"
    EVALUATING = "evaluating"
    RANKING = "ranking"
    SELECTED = "selected"
    FAILED = "failed"


@dataclass
class DecisionScore:
    """Score for a decision."""
    total: float = 0.0
    skill_match: float = 0.0
    priority: float = 0.0
    compatibility: float = 0.0
    details: Dict[str, float] = field(default_factory=dict)


@dataclass
class DecisionReason:
    """Reason for a decision."""
    rule: str
    description: str
    weight: float = 1.0


@dataclass
class DecisionResult:
    """Result of a decision — carries its evidence record (R-W1-004)."""
    decision_id: str
    status: DecisionStatus
    capability: Optional[str] = None
    provider: Optional[str] = None
    score: Optional[DecisionScore] = None
    reasons: List[DecisionReason] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    #: عقود الدليل — أثر اختيار القدرة والموفّر معاً (R-W1-004)
    records: List["DecisionRecord"] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "status": self.status.value,
            "capability": self.capability,
            "provider": self.provider,
            "score": {
                "total": self.score.total if self.score else 0,
                "skill_match": self.score.skill_match if self.score else 0,
                "priority": self.score.priority if self.score else 0
            } if self.score else None,
            "reasons": [{"rule": r.rule, "description": r.description} for r in self.reasons],
            "error": self.error,
            # R-W1-004: عقود الدليل تُصدَّر كاملة — لا تُسقط عند التسلسل
            "records": [r.to_dict() for r in self.records],
            "timestamp": self.timestamp.isoformat()
        }


class DecisionContext:
    """Context for decision."""
    
    def __init__(self, mission: Any):
        self.decision_id = str(uuid4())
        self.mission = mission
        self.required_capability = getattr(mission, "capability", "")
        self.required_skills = getattr(mission, "parameters", {}).get("required_skills", [])
        self.constraints = getattr(mission, "parameters", {}).get("constraints", [])


class DecisionValidator:
    """Validates decision context."""
    
    def validate(self, context: DecisionContext) -> List[str]:
        """Validate context."""
        errors = []
        
        if not context.required_capability:
            errors.append("Required capability is empty")
        
        return errors


class CandidateCollector:
    """Collects candidate capabilities and providers."""
    
    def __init__(self, capability_registry, provider_registry):
        self.capability_registry = capability_registry
        self.provider_registry = provider_registry
    
    def collect_capabilities(self, context: DecisionContext) -> List[Any]:
        """Collect candidate capabilities."""
        capabilities = self.capability_registry.list_all()
        
        # Filter by required capability name
        candidates = []
        for cap in capabilities:
            cap_name = getattr(cap, "name", "")
            if cap_name.lower() == context.required_capability.lower():
                candidates.append(cap)
        
        # If no exact match, include all
        if not candidates:
            candidates = capabilities
        
        return candidates
    
    def collect_providers(self, context: DecisionContext, capability: Any) -> List[Any]:
        """Collect candidate providers for a capability."""
        providers = self.provider_registry.list_all()
        
        # Filter by skills
        required_skills = getattr(capability, "skills", [])
        
        candidates = []
        for prov in providers:
            if hasattr(prov, "supports_skill"):
                # Check if provider supports all required skills
                supported = all(prov.supports_skill(s) for s in required_skills)
                if supported:
                    candidates.append(prov)
        
        return candidates or providers


class RuleEvaluator:
    """Evaluates rules for decision making."""
    
    def evaluate_capability(self, capability: Any, context: DecisionContext) -> DecisionScore:
        """Evaluate capability against context."""
        score = DecisionScore()
        
        # Skill match
        cap_skills = set(getattr(capability, "skills", []))
        req_skills = set(context.required_skills)
        
        if req_skills:
            intersection = len(cap_skills & req_skills)
            union = len(cap_skills | req_skills)
            score.skill_match = intersection / union if union > 0 else 0.5
        else:
            score.skill_match = 1.0
        
        # Name match
        cap_name = getattr(capability, "name", "").lower()
        req_name = context.required_capability.lower()
        if cap_name == req_name:
            score.skill_match = 1.0
        
        # Priority
        score.priority = getattr(capability, "priority", 1) / 10.0
        
        # Calculate total
        score.total = score.skill_match * 0.8 + score.priority * 0.2
        
        score.details = {
            "skill_match": score.skill_match,
            "priority": score.priority
        }
        
        return score
    
    def evaluate_provider(self, provider: Any, capability: Any) -> DecisionScore:
        """Evaluate provider against capability."""
        score = DecisionScore()
        
        required_skills = getattr(capability, "skills", [])
        
        if not required_skills:
            score.skill_match = 1.0
        else:
            supported = 0
            for skill in required_skills:
                if hasattr(provider, "supports_skill") and provider.supports_skill(skill):
                    supported += 1
            score.skill_match = supported / len(required_skills)
        
        score.priority = 1.0
        score.total = score.skill_match * 0.9 + score.priority * 0.1
        
        return score


class CandidateRanker:
    """Ranks candidates."""
    
    def rank_capabilities(self, candidates: List[Any], scores: List[DecisionScore]) -> List[tuple]:
        """Rank capabilities by score."""
        ranked = list(zip(candidates, scores))
        ranked.sort(key=lambda x: x[1].total, reverse=True)
        return ranked
    
    def rank_providers(self, candidates: List[Any], scores: List[DecisionScore]) -> List[tuple]:
        """Rank providers by score."""
        ranked = list(zip(candidates, scores))
        ranked.sort(key=lambda x: x[1].total, reverse=True)
        return ranked


class DecisionPipeline:
    """
    Decision Pipeline.
    
    Pipeline:
    1. Receive Context
    2. Validate Context
    3. Collect Candidate Capabilities
    4. Collect Candidate Providers
    5. Evaluate Rules
    6. Rank Candidates
    7. Select Best Option
    8. Return Decision
    
    Rules:
    ✅ Deterministic
    ✅ Repeatable
    ✅ Explainable
    ✅ Observable
    """
    
    def __init__(
        self,
        capability_registry,
        provider_registry
    ):
        self.capability_registry = capability_registry
        self.provider_registry = provider_registry
        
        self.validator = DecisionValidator()
        self.collector = CandidateCollector(capability_registry, provider_registry)
        self.evaluator = RuleEvaluator()
        self.ranker = CandidateRanker()
    
    def decide(self, context: DecisionContext) -> DecisionResult:
        """Execute the decision pipeline."""
        result = DecisionResult(
            decision_id=context.decision_id,
            status=DecisionStatus.PENDING
        )
        
        try:
            # Step 1-2: Validate context
            result.status = DecisionStatus.VALIDATING
            errors = self.validator.validate(context)
            if errors:
                result.status = DecisionStatus.FAILED
                result.error = "; ".join(errors)
                return result
            
            # Step 3: Collect capabilities — كل المسجلين مرشحون عند القلب
            # (R-W1-004: قواعد أهلية المجمّع القديم — مطابقة الاسم ثم
            # الجميع، ودعم كل المهارات ثم الجميع — ترجيح لا استبعاد، وقد
            # انتقلت إلى سلّم الأسماء وترتيب المهارات في القلب مع أثرها
            # في الدليل؛ فلا يُستبعد مرشح قبل القلب بلا مسوّى مرئي)
            result.status = DecisionStatus.COLLECTING
            capabilities = self.capability_registry.list_all()
            
            # Step 4: Evaluate capabilities
            # Step 4-5: Evaluate and rank capabilities — من القلب الموحد
            # (R-W1-004: الاختيار من DecisionCore بسياسة معلنة، والدليل
            # أثر لكل مرشح لا أفضلية صامتة)
            result.status = DecisionStatus.EVALUATING
            caps_record = DECISION_CORE.evaluate(
                DecisionRequest(
                    kind="capability",
                    requested_name=getattr(context, "required_capability", ""),
                    required_skills=list(getattr(context, "required_skills", [])
                                        or []),
                    constraints=list(getattr(context, "constraints", [])
                                     or [])),
                [DecisionCandidate(
                    name=getattr(cap, "name", ""),
                    # قراءة مؤجلة للمهارات والأولوية معاً: المستبعد بالأهلية
                    # لا تُقرأ بياناته أصلاً — كما بعد ترشيح المجمّع الأصلي؛
                    # وتعذر القراءة خطأ مسمّى داخل حماية القلب
                    skills_query=(lambda c=cap: getattr(c, "skills", [])
                                  or []),
                    priority_query=(lambda c=cap: getattr(c, "priority", 1.0)),
                    ref=cap)
                 for cap in capabilities],
                PIPELINE_CAPABILITY_POLICY,
                decision_id=f"dec-{uuid4().hex[:8]}",
                timestamp=_utc_now_iso())

            def _record_error(rec):
                # الخطأ المسجل أولوية — ثم مسوّغ الاستبعاد ثم الحالة
                if rec.errors:
                    return rec.errors[0]
                first = next((c for c in rec.candidates if c.excluded), None)
                return (first.exclusion_reason if first is not None
                        else rec.status)

            # يُحفظ أثر مرحلة القدرة فور عودتها — أي فشل لاحق لا يسقطه
            result.records = [caps_record]
            if caps_record.status != "selected":
                result.status = DecisionStatus.FAILED
                result.error = _record_error(caps_record)
                return result
            result.status = DecisionStatus.RANKING
            best_cap = next((cap for cap in capabilities
                             if getattr(cap, "name", "")
                             == caps_record.selected), None)
            best_cap_score = next(
                (c.score for c in caps_record.candidates
                 if c.name == caps_record.selected), DecisionScore())

            # Step 6: Collect providers — كل المسجلين مرشحون عند القلب
            result.status = DecisionStatus.COLLECTING
            providers = self.provider_registry.list_all()

            # Step 7-8: Evaluate and select provider — من القلب الموحد.
            # بناء محمي: فشل supports_skill في موفّر يُسمّى بالمرشح —
            # وسجل تعذر مسمّى لهذه المرحلة يُحفظ مع سجل القدرة (R-W1-004)
            required = list(getattr(best_cap, "skills", []) or [])
            # الموفّرون يُمرَّرون باستعلاماتهم فقط — مرحلتا الأصل (الترشيح
            # ثم التقييم) داخل القلب بسياسة معلنة، فقاعدة الأهلية هناك
            # تحدد المنافسة (لا هنا)
            prov_candidates = [DecisionCandidate(
                name=getattr(prov, "name", ""),
                skill_query=getattr(prov, "supports_skill",
                                    lambda _s: False),
                ref=prov)
                for prov in providers]

            prov_record = DECISION_CORE.evaluate(
                DecisionRequest(
                    kind="provider",
                    required_skills=required,
                    constraints=list(getattr(context, "constraints", [])
                                     or [])),
                prov_candidates, PIPELINE_PROVIDER_POLICY,
                decision_id=f"dec-{uuid4().hex[:8]}",
                timestamp=_utc_now_iso())
            result.records = [caps_record, prov_record]

            if prov_record.status != "selected":
                result.status = DecisionStatus.FAILED
                result.error = _record_error(prov_record)
                return result

            result.status = DecisionStatus.SELECTED
            result.capability = caps_record.selected or ""
            result.provider = prov_record.selected or ""
            result.score = best_cap_score
            result.reasons = [
                DecisionReason("skill_match", f"Skill match: {best_cap_score.skill_match:.0%}"),
                DecisionReason("priority", f"Priority: {best_cap_score.priority:.1f}"),
                DecisionReason("provider", f"Provider: {result.provider}")
            ]

            return result
            
        except Exception as e:
            result.status = DecisionStatus.FAILED
            result.error = str(e)
            return result


# ---------------------------------------------------------------------------
# R-W1-004 — قلب التقييم الموحد: سياسات معلنة + عقد دليل كامل
# ---------------------------------------------------------------------------


@dataclass
class DecisionCandidate:
    """مرشح تقييم — الكائن الأصلي يُمرَّر ولا يُقيَّم (لا آثار جانبية)."""
    name: str
    offered_skills: List[str] = field(default_factory=list)
    priority: Any = 1.0
    ref: Any = None
    #: استعلام مهارات مؤجل (سياسات الخروج المبكر — كالمحرك الأصلي):
    #: يُستعلم عن مهارة عند الحاجة إليها فقط، وبترتيب القاعدة، لا كاملاً
    skill_query: Optional[Any] = None
    #: قراءة أولوية مؤجلة: لا تُقرأ الخاصية إلا إذا استهلكتها السياسة فعلاً
    #: (المستبعد بالأهلية لا تُقرأ أولويته أصلاً — كما بعد ترشيح الأصل)
    priority_query: Optional[Any] = None
    #: قراءة مهارات مؤجلة: تُقرأ داخل حماية تقييم المرشح بعد حسم الأهلية —
    #: فالمستبعد بالأهلية لا تُقرأ مهاراته أصلاً، وتعذر القراءة خطأ مسمّى
    skills_query: Optional[Any] = None


@dataclass
class CandidateEvaluation:
    """تقييم مرشح واحد — القيم التي استخدمتها كل قاعدة، لا مجرد الدرجة."""
    name: str
    offered_skills: List[str] = field(default_factory=list)
    values_used: Dict[str, Any] = field(default_factory=dict)
    score: Optional[DecisionScore] = None
    excluded: bool = False
    exclusion_reason: str = ""
    #: تعذر تقييم هذا المرشح — موجود في الدليل بموضع فشله، لا ادعاء
    #: تقييمه ولا اعتباره مستبعداً بقواعد الأهلية
    build_failed: bool = False
    build_error: str = ""


    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "offered_skills": self.offered_skills,
                "values_used": self.values_used,
                # مكونات الدرجة كاملة — لا الإجمالي وحده
                "score": ({"total": self.score.total,
                           "skill_match": self.score.skill_match,
                           "priority": self.score.priority,
                           "details": dict(self.score.details)}
                          if self.score else None),
                "excluded": self.excluded,
                "exclusion_reason": self.exclusion_reason,
                "build_failed": self.build_failed,
                "build_error": self.build_error}


@dataclass
class DecisionPolicy:
    """سياسة قرار معلنة — هوية وإصدار وقواعد كاملة، لا ثوابت خفية.

    ``weights``: مساهمات مكونات الدرجة. ``rules``: سلّم مطابقة الأسماء،
    وشروط الأهلية، وكسر التعادل، والقيم الافتراضية المعلنة.
    """
    policy_id: str
    version: str
    kind: str                                  # capability | provider
    weights: Dict[str, float] = field(default_factory=dict)
    rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"policy_id": self.policy_id, "version": self.version,
                "kind": self.kind, "weights": dict(self.weights),
                "rules": dict(self.rules)}


@dataclass
class DecisionRequest:
    """طلب قرار — ما استُخدم فعلاً من المدخلات، لا ما ادُّعي."""
    kind: str                                  # capability | provider
    requested_name: str = ""
    required_skills: List[str] = field(default_factory=list)
    constraints: List[Any] = field(default_factory=list)


def CandidateEvaluationStub(name: str, build_error: str = "",
                            values_used: Optional[Dict[str, Any]] = None,
                            **_: Any) -> CandidateEvaluation:
    """مدخل مرشح تعذر بناؤه/تقييمه — في الدليل بموضع فشله.

    لا درجة ولا استبعاد أهلية — فقط اسمه وموضع الفشل (R-W1-004).
    """
    return CandidateEvaluation(
        name=name, build_failed=True, build_error=build_error,
        values_used=(dict(values_used) if values_used else {}))


@dataclass
class DecisionRecord:
    """عقد الدليل — كيف أدت المدخلات والقواعد والمرشحون إلى الاختيار.

    المعلومات المدخلة أو المعلنة منفصلة عن نتائج التقييم: إعلان دعمٍ
    ليس اختباراً تشغيلياً، والدرجة الحسابية ليست احتمال نجاح، والقيمة
    الافتراضية للقيود مسجلة بأصلها لا كأنها فحص.
    """
    decision_id: str
    kind: str
    requested: Dict[str, Any] = field(default_factory=dict)
    policy_id: str = ""
    policy_version: str = ""
    candidates: List[CandidateEvaluation] = field(default_factory=list)
    selected: Optional[str] = None
    ranked_alternatives: List[str] = field(default_factory=list)
    tie_break: str = ""
    #: لقطة السياسة المستخدمة (أوزانها وقواعدها) — تُحفظ عند التقييم
    policy_snapshot: Optional[Dict[str, Any]] = None
    missing_info: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "no_match"                   # selected | no_match | error
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id, "kind": self.kind,
            "requested": dict(self.requested),
            # لقطة السياسة المستخدمة: الهوية والإصدار والأوزان والقواعد
            "policy": self.policy_snapshot or {"policy_id": self.policy_id,
                                               "version": self.policy_version},
            "candidates": [c.to_dict() for c in self.candidates],
            "selected": self.selected,
            "ranked_alternatives": list(self.ranked_alternatives),
            "tie_break": self.tie_break,
            "missing_info": list(self.missing_info),
            "errors": list(self.errors),
            "status": self.status,
            "timestamp": self.timestamp,
        }


class DecisionCore:
    """قلب التقييم الموحد — لكل قرار سياسة معلنة وسجل دليل واحد.

    كل مسارات القرار تفوّض إليه (المسار الحي عبر ``resolvers/``، ومحرك
    ``decision/`` القديم، ومسار الدُبعة نفسه). حدود الاستعلام: قرارات
    الخروج المبكر (كالمحرك القديم) تستعلم مهارةً مهارةً بترتيب قاعدتها
    وتوقف عند الحسم — والاستعلام الخارجي (``skill_query``) ليس أثراً
    جانبياً داخلياً لكنه قراءة خارجية، والحتمية هنا مشروطة بثبات إجابات
    الاستعلام المسجلة في الدليل (``skills_queried``/``query_answers``).
    الترتيب حتمي: الدرجة ثم ترتيب التسجيل (فرز مستقر — كسر تعادل معلن).
    """

    version = "decision-core-1.0"

    def evaluate(self, request: DecisionRequest,
                 candidates: List[DecisionCandidate],
                 policy: DecisionPolicy, *,
                 decision_id: str,
                 timestamp: str) -> DecisionRecord:
        record = DecisionRecord(
            decision_id=decision_id, kind=request.kind,
            requested={"requested_name": request.requested_name,
                       "required_skills": list(request.required_skills),
                       "constraints": list(request.constraints)},
            policy_id=policy.policy_id, policy_version=policy.version,
            policy_snapshot=policy.to_dict(),
            timestamp=timestamp)

        # مسار الدُبعة للموفّرين: مرحلتا الأصل (ترشيح ثم تقييم) داخل القلب —
        # المحول يمرر المرشحين واستعلاماتهم فقط، وقاعدة الأهلية المعلنة
        # هي التي تحدد المنافسة (تغييرها يغير المنافسة فعلاً)
        if (request.kind == "provider"
                and policy.rules.get("provider_stages")
                == "filter-then-evaluate"
                and candidates
                and all(getattr(c, "skill_query", None) is not None
                        for c in candidates)):
            return self._evaluate_provider_stages(
                request, candidates, policy, record)
        # أهلية شرطية معلنة من سياسة الدُبعة — منقولة من المجمّع الأصلي
        # حرفياً وقبل التقييم (كما كان يرشّح قبل الحساب): إن وُجدت مطابقة
        # اسم تامة فالمنافسة محصورة فيها، وإن وُجد موفّر يدعم كل المهارات
        # فالمنافسة محصورة فيهم. المستبعد يدخل الدليل بمسوّغه — ولا تُحسب
        # درجته أصلاً (فمدخلاته قد تكون غير صالحة أصلاً للحساب)
        eligibility_excluded: Dict[str, str] = {}
        if policy.rules.get("eligibility") == "exact-name-if-available" \
                and request.requested_name:
            exact_names = {c.name for c in candidates
                          if c.name.lower()
                          == request.requested_name.lower()}
            if exact_names:
                for c in candidates:
                    if c.name not in exact_names:
                        eligibility_excluded[c.name] = (
                            "not-an-exact-name-match-"
                            "while-exact-available")
        # أهلية الموفّرين ذوي الاستعلام المؤجل تنفذها مراحلهم الخاصة
        # (عرضهم غير معروف قبل الاستعلام) — لا الخريطة العامة
        if (policy.rules.get("eligibility") == "supports-all-if-available"
                and request.required_skills
                and not all(getattr(c, "skill_query", None) is not None
                            for c in candidates)):
            full_names = {c.name for c in candidates
                          if set(request.required_skills)
                          <= set(c.offered_skills)}
            if full_names:
                for c in candidates:
                    if c.name not in full_names:
                        eligibility_excluded[c.name] = (
                            "does-not-support-all-required-"
                            "while-full-support-exists")

        # تقييم تراكمي: كل مرشح يُحفظ فور اكتماله — فشل مرشح لا يُسقط
        # أثر من سبقه، والخطأ يسمّي المرشح والمرحلة، والمرشح المتعذر
        # يبقى في الدليل بموضع فشله (لا يُدّعى تقييمه ولا استبعاده)
        evaluations: List[CandidateEvaluation] = []
        any_failed = False
        for candidate in candidates:
            # مرشحو الاستعلام المؤجل: لا تقييم مسبق — تُستعلم مهاراتهم
            # عند الحاجة فقط بترتيب قاعدة الاختيار (حدود المحرك الأصلي)،
            # فلا استبعاد بلا مهارات معروفة ولا درجة قبل الاستعلام
            if getattr(candidate, "skill_query", None) is not None:
                evaluations.append(CandidateEvaluation(
                    name=candidate.name,
                    values_used={"query_state": "not_queried"}))
                continue
            if candidate.name in eligibility_excluded:
                evaluations.append(CandidateEvaluation(
                    name=candidate.name,
                    offered_skills=list(candidate.offered_skills),
                    excluded=True,
                    exclusion_reason=eligibility_excluded[candidate.name],
                    values_used={"excluded_by":
                                 "conditional-eligibility-before-evaluation"}))
                continue
            try:
                evaluations.append(self._evaluate_candidate(
                    candidate, request, policy, record))
            except Exception as exc:  # noqa: BLE001 — خطأ مسمّى
                # المرشح المتعذر يبقى في الدليل بموضع فشله — واللاحقون
                # يُقيَّمون ويُحفظون بترتيبهم (لا يختفي أحد)؛ والتعذر
                # يمنع إثبات الفائز فلا اختيار
                any_failed = True
                record.errors.append(
                    f"candidate {candidate.name}: stage=evaluation "
                    f"{type(exc).__name__}: {exc}")
                evaluations.append(CandidateEvaluation(
                    name=candidate.name,
                    offered_skills=list(candidate.offered_skills),
                    build_failed=True,
                    build_error=f"evaluation: {type(exc).__name__}: {exc}",
                    values_used={"failed_stage": "evaluation"}))
        record.candidates = evaluations
        if any_failed:
            record.status = "error"
            record.selected = None
            record.ranked_alternatives = []
            return record

        eligible = [e for e in evaluations
                    if not e.excluded and not e.build_failed]
        if not eligible:
            record.status = "no_match"
            if not candidates:
                record.missing_info.append("no-candidates-registered")
            return record

        # قاعدة اختيار معلنة تتحكم فعلاً: أول موفّر بترتيب التسجيل يدعم
        # أول مهارة مطلوبة (قاعدة المحرك القديم decision/) — والترتيب
        # المعلن للبدائل وفقها: أول مهارة مدعومة ثم ترتيب التسجيل
        if policy.rules.get("selection") == \
                "first-in-registration-order-supporting-a-skill":
            # بلا مهارات مطلوبة لا قاعدة تختار — فشل المحرك القديم محفوظ
            if not request.required_skills:
                record.status = "no_match"
                return record
            # استعلام مؤجل بحدود المحرك الأصلي: مهارةً مهارةً بترتيب
            # الطلب، وموفّراً موفّراً بترتيب التسجيل، وأول دعم يفوز
            # ويُوقف الاستعلام (لا يُسأل من بعده عن مهارة لاحقة أصلاً)
            if any(getattr(c, "skill_query", None) is not None
                   for c in candidates):
                # دليل الاستعلام: لكل مرشح المهارات التي سُئل عنها فعلاً
                # وإجاباتها — والمرشح الذي حسم والمرحلة التي فشل فيها
                eval_by_name = {e.name: e for e in evaluations}
                for skill in request.required_skills:
                    for cand in candidates:
                        if cand.name in eligibility_excluded:
                            continue
                        try:
                            supported = bool(cand.skill_query(skill))
                        except Exception as exc:  # noqa: BLE001
                            # المرشح نفسه يوسم بالتعذر — والمحاولة الفاشلة
                            # مسجلة (المهارة والخطأ) لا الناجحة وحدها
                            record.errors.append(
                                f"candidate {cand.name}: "
                                f"stage=skill-query({skill}) "
                                f"{type(exc).__name__}: {exc}")
                            ev = eval_by_name.get(cand.name)
                            if ev is not None:
                                ev.build_failed = True
                                ev.build_error = (
                                    f"skill-query({skill}): "
                                    f"{type(exc).__name__}: {exc}")
                                ev.values_used["failed_stage"] = \
                                    f"skill-query({skill})"
                                ev.values_used["query_state"] = "failed"
                                ev.values_used["failed_query"] = {
                                    "skill": skill,
                                    "error": f"{type(exc).__name__}: {exc}"}
                            record.status = "error"
                            record.selected = None
                            return record
                        ev = eval_by_name.get(cand.name)
                        if ev is not None:
                            ev.values_used.setdefault(
                                "skills_queried", []).append(skill)
                            ev.values_used.setdefault(
                                "query_answers", {})[skill] = supported
                            ev.values_used["query_state"] = "queried"
                        if supported:
                            record.selected = cand.name
                            record.ranked_alternatives = [cand.name]
                            record.tie_break = \
                                "first-required-skill-then-registration-order"
                            if ev is not None:
                                ev.values_used["decided_by_skill"] = skill
                                ev.values_used["query_state"] = "decided"
                            # المهارات المتبقية بعد الحسم معلنة إن وُجدت —
                            # لا تضاف دائماً (موفّر واحد ومهارة واحدة
                            # مدعومة لا استعلامات متبقية)
                            idx = list(request.required_skills).index(skill)
                            remaining = list(request.required_skills)[idx + 1:]
                            if remaining:
                                record.missing_info.append(
                                    "skills-not-queried-after-decision:"
                                    f"{cand.name}:{remaining}")
                            record.status = "selected"
                            return record
                record.status = "no_match"
                return record

            def _first_skill_index(e):
                for i, skill in enumerate(request.required_skills):
                    if skill in e.offered_skills:
                        return i
                return len(request.required_skills)

            ordered = sorted(eligible, key=_first_skill_index)
            record.selected = ordered[0].name
            record.ranked_alternatives = [e.name for e in ordered]
            record.tie_break = "first-required-skill-then-registration-order"
            record.status = "selected"
            return record

        ranked = sorted(eligible, key=lambda e: -e.score.total)
        # كسر التعادل: فرز مستقر — ترتيب التسجيل (معلن في قواعد السياسة)
        ties = [e for e in ranked
                if abs(e.score.total - ranked[0].score.total) < 1e-12]
        if len(ties) > 1:
            record.tie_break = policy.rules.get(
                "tie_break", "stable-registration-order")
        record.selected = ranked[0].name
        record.ranked_alternatives = [e.name for e in ranked]
        record.status = "selected"
        return record

    def _evaluate_provider_stages(self, request, candidates, policy, record):
        """مرحلتا مسار الدُبعة داخل القلب — الترشيح ثم التقييم.

        الترشيح: تطبيق قاعدة الأهلية المعلنة (``supports-all-if-available``)
        بحدود فحص all() الأصلي (وقف عند أول غير مدعوم). التقييم: استعلام كل
        المهارات لكل منافس — حتى المجتازين (كما في مُقيّم الأصل الذي كان
        يستعلم كل المهارات بعد الترشيح). ولكل مرشح حالته في الدليل بترتيب
        تسجيله: تعذر (بمرحلته) / مستبعد بالفحص (بحدود استعلامه) / مُقيَّم
        (بقيم كل قاعدة وحدود استعلام كل مرحلة).
        """
        required = list(request.required_skills)
        if not required:
            # بلا مهارات مطلوبة لا فحص يُرشِّح — الجميع منافسون (كالأصل
            # عند سقوط الفحص لعدم وجود مهارات)
            pass
        # المرحلة الأولى: الترشيح بحدود فحص all()
        entries = []  # (cand, state, filter_queried, exc)
        if required and policy.rules.get("eligibility") == \
                "supports-all-if-available":
            for cand in candidates:
                queried = []
                passed = True
                try:
                    for s in required:
                        queried.append(s)
                        if not cand.skill_query(s):
                            passed = False
                            break
                except Exception as exc:  # noqa: BLE001 — خطأ مسمّى
                    record.errors.append(
                        f"candidate {cand.name}: stage=filtering "
                        f"{type(exc).__name__}: {exc}")
                    entries.append((cand, "failed_filter", queried, exc))
                    continue
                entries.append((cand, "passed" if passed else "filtered_out",
                               queried, None))
        else:
            # لا قاعدة أهلية معلنة — لا ترشيح: الجميع منافسون
            entries = [(c, "passed", [], None) for c in candidates]

        passers = [c for c, state, _, _ in entries if state == "passed"]
        # المنافسة: المجتازون إن وُجدوا — وإلا الجميع (عودة الأصل)
        competing_states = ("passed",) if passers else ("passed",
                                                        "filtered_out")

        # المرحلة الثانية: التقييم — استعلام كل المهارات لكل منافس
        final: List[CandidateEvaluation] = []
        any_failed = False
        for cand, state, filter_queried, filter_exc in entries:
            if state == "failed_filter":
                final.append(CandidateEvaluation(
                    name=cand.name,
                    build_failed=True,
                    build_error=f"filtering: {type(filter_exc).__name__}: "
                               f"{filter_exc}",
                    values_used={"failed_stage": "filtering",
                                 "filter_queried": list(filter_queried)}))
                any_failed = True
                continue
            if state == "filtered_out" and passers:
                # مستبعد بالفحص: ظاهر بمسوّغ وحدود استعلامه — «لم يُسأل»
                # لا تساوي «غير مدعوم»
                final.append(CandidateEvaluation(
                    name=cand.name, excluded=True,
                    exclusion_reason="did-not-pass-all-skills-filter",
                    values_used={"query_stages": {
                        "filtering": list(filter_queried),
                        "evaluation": []},
                        "note": "not-queried-beyond-filter"}))
                continue
            # منافس — استعلام تقييم كامل (كما في مُقيّم الأصل)
            offered = []
            evaluation_queried = []
            try:
                for s in required:
                    evaluation_queried.append(s)
                    if cand.skill_query(s):
                        offered.append(s)
            except Exception as exc:  # noqa: BLE001 — خطأ مسمّى
                record.errors.append(
                    f"candidate {cand.name}: stage=evaluation-queries "
                    f"{type(exc).__name__}: {exc}")
                final.append(CandidateEvaluation(
                    name=cand.name,
                    build_failed=True,
                    build_error=f"evaluation-queries: "
                               f"{type(exc).__name__}: {exc}",
                    values_used={"failed_stage": "evaluation-queries",
                                 "filter_queried": list(filter_queried),
                                 "evaluation_queried":
                                     list(evaluation_queried)}))
                any_failed = True
                continue
            try:
                evaluation = self._evaluate_provider(
                    replace(cand, offered_skills=offered), request, policy,
                    record)
            except Exception as exc:  # noqa: BLE001 — خطأ مسمّى
                # حماية الحساب لا الاستعلام وحده: فشل قاعدة حسابية
                # يُسمّى بالمرشح ومرحلته — لا استثناء يسقط السجل كله
                record.errors.append(
                    f"candidate {cand.name}: stage=evaluation "
                    f"{type(exc).__name__}: {exc}")
                final.append(CandidateEvaluation(
                    name=cand.name,
                    build_failed=True,
                    build_error=f"evaluation: {type(exc).__name__}: {exc}",
                    values_used={"failed_stage": "evaluation",
                                 "filter_queried": list(filter_queried),
                                 "evaluation_queried":
                                     list(evaluation_queried)}))
                any_failed = True
                continue
            evaluation.values_used["query_stages"] = {
                "filtering": list(filter_queried),
                "evaluation": list(evaluation_queried)}
            final.append(evaluation)

        record.candidates = final
        if any_failed:
            # تعذر مرحلي يمنع إثبات الفائز — لا اختيار، والدليل كامل
            record.status = "error"
            record.selected = None
            record.ranked_alternatives = []
            return record

        eligible = [e for e in final
                    if not e.excluded and not e.build_failed]
        if not eligible:
            record.status = "no_match"
            if not candidates:
                record.missing_info.append("no-candidates-registered")
            return record

        ranked = sorted(eligible, key=lambda e: -e.score.total)
        ties = [e for e in ranked
                if abs(e.score.total - ranked[0].score.total) < 1e-12]
        if len(ties) > 1:
            record.tie_break = policy.rules.get(
                "tie_break", "stable-registration-order")
        record.selected = ranked[0].name
        record.ranked_alternatives = [e.name for e in ranked]
        record.status = "selected"
        return record

    def _evaluate_candidate(self, candidate: DecisionCandidate,
                            request: DecisionRequest,
                            policy: DecisionPolicy,
                            record: DecisionRecord) -> CandidateEvaluation:
        if policy.kind == "capability":
            return self._evaluate_capability(candidate, request, policy, record)
        return self._evaluate_provider(candidate, request, policy, record)

    def _evaluate_capability(self, candidate, request, policy, record):
        # قراءة المهارات مؤجلة إلى هنا — داخل حماية تقييم المرشح وبعد
        # حسم الأهلية (القلب): فالمستبعد بالأهلية لا تُقرأ مهاراته أصلاً،
        # وتعذر قراءتها خطأ مسمّى بهذا المرشح لا استثناء عارياً
        if getattr(candidate, "skills_query", None) is not None:
            offered_skills = list(candidate.skills_query() or [])
        else:
            offered_skills = list(candidate.offered_skills)
        evaluation = CandidateEvaluation(
            name=candidate.name,
            offered_skills=offered_skills)
        weights = policy.weights
        rules = policy.rules
        requested = request.requested_name.lower()
        name = candidate.name.lower()
        # حساب مسار الدُفعة منقول حرفياً من المُقيّم الأصلي (جاكار مع
        # تجاوز الاسم التام، وبلا مهارات مطلوبة الجميع 1.0) — لا سلّم
        # أسماء المسار الحي، ولا استبعاد (الأهلية الشرطية في evaluate)
        if rules.get("capability_scoring") == "jaccard-exact-override":
            if requested and requested == name:
                skill_match = 1.0
            elif not request.required_skills:
                skill_match = 1.0
            else:
                offered = set(offered_skills)
                required = set(request.required_skills)
                union = offered | required
                skill_match = (len(offered & required) / len(union)
                               if union else 0.5)
            evaluation.score = DecisionScore(
                total=skill_match * weights.get("skill", 1.0),
                skill_match=skill_match)
            # الأولوية للقدرة حقيقية في مسار الدُبعة (كالأصل)
            evaluation.values_used = {
                "scoring": "jaccard-exact-override",
                "skill_match": skill_match}
            if rules.get("eligibility") != "exact-name-if-available":
                # لا استبعاد في حساب الدُفعة — الأهلية الشرطية في evaluate
                pass
            # تُكمل الحساب بالقيود والأولوية أدناه (مسار موحد)
            constraint_contribution = weights.get("constraint", 0.0)
            constraint_label = "declared-default-unevaluated"
            if request.constraints:
                record.missing_info.append(
                    f"constraints-not-evaluated:{candidate.name}")
            if getattr(candidate, "priority_query", None) is not None:
                _p = candidate.priority_query()
            else:
                _p = getattr(candidate, "priority", 1.0)
            priority = (float(_p) if _p is not None else 1.0) / 10.0
            total = (skill_match * weights.get("skill", 1.0)
                     + priority * weights.get("priority_weight", 0.0))
            evaluation.score = DecisionScore(
                total=total, skill_match=skill_match, priority=priority)
            return evaluation
        ladder = policy.rules.get("name_match",
                                  {"exact": 1.0, "requested_in_name": 0.8,
                                   "name_in_requested": 0.6})
        skill_match = 0.0
        if requested and requested == name:
            skill_match = ladder["exact"]
        elif requested and requested in name:
            skill_match = ladder["requested_in_name"]
        elif requested and name in requested:
            skill_match = ladder["name_in_requested"]
        elif request.required_skills:
            offered = set(offered_skills)
            required = set(request.required_skills)
            union = offered | required
            skill_match = (len(offered & required) / len(union)
                           if union else 0.0)
        # لا علاقة اسماً ولا مهارات — ليس مرشحاً: استبعاد مسمّى لا افتراضي.
        # بيانات المستبعد: ما قرئ فعلاً لا ادعاء فحص — والفرق بين مهارات
        # قُرئت وكانت فارغة ومهارات لم تُقرأ ظاهر في الدليل
        if skill_match == 0.0:
            evaluation.excluded = True
            evaluation.exclusion_reason = (
                "no-name-or-skill-relationship")
            evaluation.values_used = {
                "requested_name": request.requested_name,
                "offered_skills_read": list(offered_skills),
                "skills_source": ("skills_query"
                                  if getattr(candidate, "skills_query",
                                             None) is not None
                                  else "candidate-offered")}
            return evaluation

        # القيود: مساهمة افتراضية معلنة — ليست فحصاً (تُعلن في missing_info)
        constraint_contribution = weights.get("constraint", 0.0)
        constraint_label = "declared-default-unevaluated"
        if request.constraints:
            record.missing_info.append(
                f"constraints-not-evaluated:{candidate.name}")
        # قراءة مؤجلة: الخاصية لا تُلمس إلا إذا استهلكتها السياسة —
        # داخل حماية تقييم المرشح في evaluate()
        if getattr(candidate, "priority_query", None) is not None:
            _p = candidate.priority_query()
        else:
            _p = getattr(candidate, "priority", 1.0)
        priority = (float(_p) if _p is not None else 1.0) / 10.0
        total = (skill_match * weights.get("skill", 1.0)
                 + constraint_contribution * weights.get("constraint_weight", 0.0)
                 + priority * weights.get("priority_weight", 0.0))
        score = DecisionScore(total=total, skill_match=skill_match,
                              priority=priority,
                              details={"skill_match": skill_match,
                                       "constraint_contribution":
                                           constraint_contribution,
                                       "priority": priority})
        evaluation.score = score
        evaluation.values_used = {
            "requested_name": request.requested_name,
            "required_skills": list(request.required_skills),
            "skill_match": skill_match,
            # مصدر المهارات المقروءة معلن — فالفرق بين قُرئت فارغة
            # ولم تُقرأ ظاهر في الدليل
            "offered_skills_read": list(offered_skills),
            "skills_source": ("skills_query"
                              if getattr(candidate, "skills_query",
                                         None) is not None
                              else "candidate-offered"),
            "constraint_contribution": constraint_contribution,
            "priority": priority}
        return evaluation

    def _evaluate_provider(self, candidate, request, policy, record):
        evaluation = CandidateEvaluation(
            name=candidate.name,
            offered_skills=list(candidate.offered_skills))
        weights = policy.weights
        required = list(request.required_skills)
        supported = [s for s in required if s in candidate.offered_skills]
        if required:
            skill_match = len(supported) / len(required)
            if skill_match == 0.0:
                # موفّر بلا دعم لأي مهارة مطلوبة — ليس مرشحاً (سلوك مصحح
                # موثق: كان يُختار بدرجة موجبة من مساهمات افتراضية)
                evaluation.excluded = True
                evaluation.exclusion_reason = "no-required-skill-support"
                evaluation.values_used = {
                    "required_skills": required,
                    "supported_skills": []}
                return evaluation
        else:
            # سلوك المسار القديم محفوظ حرفياً: بلا مهارات مطلوبة الجميع
            # درجتهم 1.0 والاختيار بترتيب التسجيل — الأولوية لا تؤثر
            skill_match = 1.0
            # القيود تُعلن غير مُقيَّمة حتى في هذا الفرع — لا تُخفى
            if request.constraints:
                record.missing_info.append(
                    f"constraints-not-evaluated:{candidate.name}")
            evaluation.score = DecisionScore(total=1.0, skill_match=1.0)
            evaluation.values_used = {
                "required_skills": [], "supported_skills": [],
                "skill_match": 1.0, "total": 1.0,
                "note": "no-required-skills-all-equal-registration-order"}
            return evaluation
        constraint_contribution = weights.get("constraint", 0.0)
        constraint_label = "declared-default-unevaluated"
        if request.constraints:
            record.missing_info.append(
                f"constraints-not-evaluated:{candidate.name}")
        if policy.rules.get("priority_contribution") == "constant-1.0":
            # مسار الدُبعة الأصلي: أولوية الموفّر غير مقروءة أصلاً —
            # مساهمة ثابتة من القيم المعلنة في السياسة نفسها (priority
            # الثابتة × معاملها المعلن): الدرجة قابلة لإعادة الحساب من
            # لقطة السياسة والقيم المسجلة، ولا حرفية خفية
            priority = 1.0
            priority_basis = "constant-1.0-not-read"
            total = (skill_match * weights.get("skill", 1.0)
                     + constraint_contribution
                     * weights.get("constraint_weight", 0.0)
                     + priority * weights.get("priority_weight", 0.0))
        elif policy.rules.get("priority_contribution") == "unused":
            # قاعدة المحرك القديم: الأولوية غير المستهلكة لا تُقرأ ولا تُحوَّل
            priority = 0.0
            priority_basis = "unused-not-read"
            total = (skill_match * weights.get("skill", 1.0)
                     + constraint_contribution
                     * weights.get("constraint_weight", 0.0))
        else:
            # قراءة مؤجلة: الخاصية لا تُلمس إلا إذا استهلكتها السياسة —
            # داخل حماية تقييم المرشح في evaluate()
            if getattr(candidate, "priority_query", None) is not None:
                _p = candidate.priority_query()
            else:
                _p = getattr(candidate, "priority", 1.0)
            priority = (float(_p) if _p is not None else 1.0) / 10.0
            priority_basis = "candidate-priority"
            total = (skill_match * weights.get("skill", 1.0)
                     + constraint_contribution
                     * weights.get("constraint_weight", 0.0)
                     + priority * weights.get("priority_weight", 0.0))
        score = DecisionScore(total=total, skill_match=skill_match,
                              priority=priority,
                              details={"skill_match": skill_match,
                                       "supported_skills": supported,
                                       "constraint_contribution":
                                           constraint_contribution,
                                       "priority": priority})
        evaluation.score = score
        evaluation.values_used = {
            "required_skills": required,
            "supported_skills": supported,
            "skill_match": skill_match,
            "constraint_contribution": {
                "value": constraint_contribution,
                "basis": constraint_label},
            "priority": priority,
            "priority_basis": priority_basis}
        return evaluation


#: سياسة المسار الحي — اختيار القدرة (سلّم الأسماء، أوزان resolvers)
LIVE_CAPABILITY_POLICY = DecisionPolicy(
    policy_id="live-capability-resolution", version="1.0.0", kind="capability",
    weights={"skill": 0.7, "constraint": 1.0, "constraint_weight": 0.2,
             "priority_weight": 0.1},
    rules={"name_ladder": "exact=1.0, requested-in-name=0.8, "
                          "name-in-requested=0.6, skills-jaccard",
           "name_match": {"exact": 1.0, "requested_in_name": 0.8,
                          "name_in_requested": 0.6},
           "exclusion": "no-name-or-skill-relationship",
           "tie_break": "stable-registration-order",
           "constraint_contribution": "declared-default-not-evaluated"})

#: سياسة المسار الحي — اختيار الموفّر (أوزان resolvers نفسها)
LIVE_PROVIDER_POLICY = DecisionPolicy(
    policy_id="live-provider-resolution", version="1.0.0", kind="provider",
    weights={"skill": 0.8, "constraint": 1.0, "constraint_weight": 0.1,
             "priority_weight": 0.1},
    rules={"exclusion": "no-required-skill-support",
           "tie_break": "stable-registration-order",
           "constraint_contribution": "declared-default-not-evaluated"})

#: سياسة المحرك القديم decision/ — أول موفّر يدعم مهارة (بالترتيب)
FIRST_PROVIDER_POLICY = DecisionPolicy(
    policy_id="first-provider-for-skill", version="1.0.0", kind="provider",
    weights={"skill": 1.0, "constraint": 0.0, "constraint_weight": 0.0,
             "priority_weight": 0.0},
    rules={"exclusion": "no-required-skill-support",
           "tie_break": "stable-registration-order",
           "priority_contribution": "unused",
           "selection": "first-in-registration-order-supporting-a-skill"})

#: سياسة مسار الدُفعة ``decision-pipeline`` — أوزان مساره المعلنة (R-W1-004).
#: قواعد الأهلية الشرطية منقولة من المجمّع الأصلي حرفياً (لا تقريب أوزان):
#: إن وُجدت مطابقة اسم تامة فالمنافسة محصورة فيها، وحساب القدرة
#: بجاكار مع تجاوز الاسم التام — لا سلّم أسماء المسار الحي.
PIPELINE_CAPABILITY_POLICY = DecisionPolicy(
    policy_id="pipeline-capability-selection", version="1.0.0",
    kind="capability",
    weights={"skill": 0.8, "constraint": 0.0, "priority": 0.2,
             "constraint_weight": 0.0, "priority_weight": 0.2},
    rules={"capability_scoring": "jaccard-exact-override",
           "eligibility": "exact-name-if-available",
           "tie_break": "stable-registration-order"})

PIPELINE_PROVIDER_POLICY = DecisionPolicy(
    policy_id="pipeline-provider-selection", version="1.0.0",
    kind="provider",
    # أولوية ثابتة 1.0 بمعاملها المعلن 0.1 — كما في الأصل حرفياً
    # (total = skill*0.9 + 0.1)؛ أولوية الموفّر غير مقروءة أصلاً
    weights={"skill": 0.9, "constraint": 0.0, "priority": 1.0,
             "constraint_weight": 0.0, "priority_weight": 0.1},
    rules={"eligibility": "supports-all-if-available",
           "provider_stages": "filter-then-evaluate",
           "priority_contribution": "constant-1.0",
           "tie_break": "stable-registration-order"})

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


#: المحرك الموحد المشترك (قلب خالٍ من الحالة — يُنشأ لكل استدعاء)
DECISION_CORE = DecisionCore()
