"""Resolvers for Capabilities and Providers."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from context import ExecutionContext
from interfaces import ICapability, IProvider
from mission import Mission
from registry.capability import CapabilityRegistry
from registry.provider import ProviderRegistry

import uuid as _uuid


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _score_from_evaluation(evaluation) -> "SelectionScore":
    """درجة التقييم الموحد إلى شكل SelectionScore — نفس الحقول التوافقة."""
    score = evaluation.score
    return SelectionScore(
        total=score.total if score else 0.0,
        skill_match=score.skill_match if score else 0.0,
        constraint_match=(score.details.get("constraint_contribution", 0.0)
                          if score else 0.0),
        priority=score.priority if score else 0.0,
        details=dict(score.details) if score else {})


class ResolutionStatus(Enum):
    """Resolution status."""
    SUCCESS = "success"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"


@dataclass
class SelectionScore:
    """Score for a selection."""
    total: float = 0.0
    skill_match: float = 0.0
    constraint_match: float = 0.0
    priority: float = 0.0
    details: Dict[str, float] = field(default_factory=dict)


@dataclass
class CapabilitySelection:
    """Result of capability resolution — carries its evidence record."""
    capability: ICapability
    capability_name: str
    manifest_id: str
    status: ResolutionStatus
    score: SelectionScore
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    #: عقد الدليل من المسار الموحد (R-W1-004) — كيف اختيرت هذه القدرة
    record: Any = None


@dataclass
class ProviderSelection:
    """Result of provider resolution — carries its evidence record."""
    provider: IProvider
    provider_name: str
    status: ResolutionStatus
    score: SelectionScore
    reason: str
    supported_skills: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    #: عقد الدليل من المسار الموحد (R-W1-004) — كيف اختير هذا الموفّر
    record: Any = None


class CapabilityResolver:
    """Resolves the best capability for a mission. Deterministic, no AI, no randomness."""
    
    def __init__(self, capability_registry: CapabilityRegistry):
        self.capability_registry = capability_registry
    
    def resolve(
        self,
        mission: Mission,
        context: Optional[ExecutionContext] = None
    ) -> CapabilitySelection:
        """Resolve the best capability for a mission.

        R-W1-004: التقييم والاختيار من المسار الموحد (``DecisionCore``)
        بسياسة المسار الحي المعلنة — والدليل كامل في ``record``. سلوكان
        صُلحا ووثّقا: المرشح بلا علاقة اسم ولا مهارات يُستبعد بمسوّى
        مسمّى (كان يُختار أفضلُ غيرِ مناسب افتراضياً)، والقيود مساهمة
        افتراضية معلنة لا فحص.
        """
        from decision_pipeline import (DECISION_CORE, DecisionCandidate,
                                        CandidateEvaluationStub, DecisionRequest,
                                        LIVE_CAPABILITY_POLICY)
        requested_capability = mission.capability
        required_skills = mission.parameters.get("required_skills", [])
        constraints = mission.parameters.get("constraints", [])

        registered = self.capability_registry.list_all()
        # بناء محمي: فشل تحويل أولوية قدرة يُسمّى ولا يُسقط القرار —
        # والمتعذر يبقى في الدليل بموضع فشله
        # الأولوية خام: القلب يحوّلها داخل حمايته عند الحاجة — فتعذر
        # التحويل يُسمّى هناك بموضعه ولا يُسقط القرار من المحول
        # قراءة مؤجلة للمهارات والأولوية معاً: تُقرآن داخل حماية القلب عند
        # تقييم المرشح — فتعذر القراءة خطأ مسمّى بالمرشح لا استثناء عارياً
        candidates = [DecisionCandidate(
            name=cap.name,
            skills_query=(lambda c=cap: getattr(c, "skills", [])),
            priority_query=(lambda c=cap: getattr(c, "priority", 1.0)),
            ref=cap)
            for cap in registered]

        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="capability",
                            requested_name=requested_capability,
                            required_skills=list(required_skills),
                            constraints=list(constraints)),
            candidates, LIVE_CAPABILITY_POLICY,
            decision_id=f"cap-{_uuid.uuid4()}", timestamp=_utc_now_iso())

        if record.status == "error":
            # تعذر التقييم ≠ عدم المطابقة — يُبلَّغ الخطأ المسمّى ولا يُسقط الدليل
            return CapabilitySelection(
                capability=None, capability_name="", manifest_id="",
                status=ResolutionStatus.ERROR, score=SelectionScore(),
                reason=(record.errors[0] if record.errors
                        else "capability evaluation error"),
                record=record)
        if record.status != "selected" or record.selected is None:
            reason = ("No capabilities registered" if not registered
                     else "No capability matches the requirements")
            return CapabilitySelection(
                capability=None, capability_name="", manifest_id="",
                status=ResolutionStatus.NO_MATCH, score=SelectionScore(),
                reason=reason, record=record)

        best = next(c for c in candidates if c.name == record.selected)
        best_capability = best.ref
        best_score = _score_from_evaluation(
            next(e for e in record.candidates if e.name == record.selected))
        return CapabilitySelection(
            capability=best_capability,
            capability_name=best_capability.name,
            manifest_id=getattr(best_capability, "id", best_capability.name),
            status=ResolutionStatus.SUCCESS,
            score=best_score,
            reason=self._generate_reason(
                best_capability, best_score, requested_capability),
            record=record)
    
    def _calculate_score(self, capability: ICapability, requested: str,
                         required_skills: List[str], mission: Mission) -> SelectionScore:
        """Calculate match score for a capability."""
        score = SelectionScore()
        
        if capability.name.lower() == requested.lower():
            score.skill_match = 1.0
        elif requested.lower() in capability.name.lower():
            score.skill_match = 0.8
        elif capability.name.lower() in requested.lower():
            score.skill_match = 0.6
        else:
            capability_skills = set(capability.skills)
            required_set = set(required_skills)
            if required_set:
                intersection = len(capability_skills & required_set)
                union = len(capability_skills | required_set)
                score.skill_match = intersection / union if union > 0 else 0.0
            else:
                score.skill_match = 0.3
        
        score.constraint_match = 1.0
        priority = getattr(capability, "priority", 1.0)
        score.priority = priority / 10.0
        
        score.total = (score.skill_match * 0.7 + score.constraint_match * 0.2 + score.priority * 0.1)
        score.details = {"skill_match": score.skill_match, "constraint_match": score.constraint_match, "priority": score.priority}
        
        return score
    
    def _generate_reason(self, capability: ICapability, score: SelectionScore, requested: str) -> str:
        """Generate human-readable reason for selection."""
        if capability.name.lower() == requested.lower():
            return "Exact name match"
        return f"Best skill match ({score.skill_match:.0%})"


class ProviderResolver:
    """Resolves the best provider for a capability. Deterministic, no AI, no randomness."""
    
    def __init__(self, provider_registry: ProviderRegistry, capability_registry: CapabilityRegistry):
        self.provider_registry = provider_registry
        self.capability_registry = capability_registry
    
    def resolve(self, capability: ICapability, mission: Optional[Mission] = None) -> ProviderSelection:
        """Resolve the best provider for a capability.

        R-W1-004: التقييم والاختيار من المسار الموحد (``DecisionCore``)
        بسياسة المسار الحي المعلنة — والدليل كامل في ``record``. سلوك
        صُلح ووثّق: الموفّر بلا دعم لأي مهارة مطلوبة يُستبعد بمسوّى مسمّى
        (كانت مساهمات الأولوية والقيود الافتراضية تكفيه درجةً موجبة
        فيُختار وقد لا يدعم شيئاً).
        """
        from decision_pipeline import (DECISION_CORE, DecisionCandidate,
                                        CandidateEvaluationStub, DecisionRequest,
                                        LIVE_PROVIDER_POLICY)
        required_skills = list(getattr(capability, "skills", []))
        constraints = (mission.parameters.get("constraints", [])
                      if mission is not None else [])

        # بناء محمي: فشل supports_skill أو تحويل الأولوية في موفّر لا يُسقط
        # القرار كله — يُسمّى الخطأ ويُحفظ الدليل (R-W1-004)
        # استعلام كامل كما في المسار الحي الأصلي (لا خروج مبكر) —
        # والأولوية خام: القلب يحوّلها داخل حمايته عند الحاجة فقط،
        # ففرع «بلا مهارات مطلوبة» لا يقرأها أصلاً
        candidates = []
        build_errors = []
        failed_stubs = []
        provider_order = []
        for provider in self.provider_registry.list_all():
            provider_order.append(provider.name)
            try:
                offered = [s for s in required_skills
                           if provider.supports_skill(s)]
                candidates.append(DecisionCandidate(
                    name=provider.name, offered_skills=offered,
                    priority_query=(lambda p=provider: getattr(p, "priority", 1.0)),
                    ref=provider))
            except Exception as exc:  # noqa: BLE001 — خطأ بناء مسمّى
                build_errors.append(
                    f"candidate {getattr(provider, 'name', '?')}: "
                    f"stage=candidate-building {type(exc).__name__}: {exc}")
                failed_stubs.append((getattr(provider, "name", "?"),
                                    type(exc).__name__, str(exc)))

        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", requested_name="",
                            required_skills=required_skills,
                            constraints=list(constraints)),
            candidates, LIVE_PROVIDER_POLICY,
            decision_id=f"prov-{_uuid.uuid4()}", timestamp=_utc_now_iso())
        if build_errors:
            # تعذر بناء مرشح يمنع إثبات الفائز — لا اختيار مع جهل مرشح
            # (قد يكون المتعذر هو الفائز): خطأ مسمّى بلا مختار، والمتعذر
            # في الدليل بموضع فشله، والنقص مسمّى بالخطأ لا بادعاء غياب
            # التسجيل
            record.errors.extend(build_errors)
            stub_by_name = {
                name: CandidateEvaluationStub(
                    name=name, build_failed=True,
                    build_error=f"candidate-building: {etype}: {msg}",
                    values_used={"failed_stage": "candidate-building"})
                for name, etype, msg in failed_stubs}
            core_by_name = {e.name: e for e in record.candidates}
            # المتعذر في الدليل بترتيب تسجيله الأصلي — لا ملحقاً بالآخرين
            record.candidates = [
                stub_by_name.get(name, core_by_name.get(name))
                for name in provider_order]
            record.selected = None
            record.ranked_alternatives = []
            record.status = "error"
            record.missing_info = [m for m in record.missing_info
                                   if m != "no-candidates-registered"]

        if record.status == "error":
            return ProviderSelection(
                provider=None, provider_name="", status=ResolutionStatus.ERROR,
                score=SelectionScore(),
                reason=(record.errors[0] if record.errors
                        else "provider evaluation error"),
                record=record)
        if record.status != "selected" or record.selected is None:
            return ProviderSelection(
                provider=None, provider_name="", status=ResolutionStatus.NO_MATCH,
                score=SelectionScore(), reason="No providers support required skills",
                record=record)

        best = next(c for c in candidates if c.name == record.selected)
        best_provider = best.ref
        best_evaluation = next(e for e in record.candidates
                               if e.name == record.selected)
        best_score = _score_from_evaluation(best_evaluation)
        # R-W3-001: مهارات الموفّر المختار — من القيم المُقيَّمة فعلاً في
        # الدليل، لا بإعادة استدعاء supports_skill خارج حماية البناء
        supported_skills = list(
            best_evaluation.values_used.get("supported_skills", []))
        return ProviderSelection(
            provider=best_provider,
            provider_name=best_provider.name,
            status=ResolutionStatus.SUCCESS,
            score=best_score,
            reason=self._generate_reason(best_provider, best_score, required_skills),
            supported_skills=supported_skills,
            record=record
        )
    
    def _calculate_score(self, provider: IProvider, required_skills: List[str]) -> SelectionScore:
        """Calculate match score for a provider."""
        score = SelectionScore()
        
        if not required_skills:
            score.total = 1.0
            return score
        
        supported = sum(1 for s in required_skills if provider.supports_skill(s))
        score.skill_match = supported / len(required_skills)
        score.constraint_match = 1.0
        priority = getattr(provider, "priority", 1.0)
        score.priority = priority / 10.0
        
        score.total = (score.skill_match * 0.8 + score.constraint_match * 0.1 + score.priority * 0.1)
        score.details = {"skill_match": score.skill_match, "supported_skills": supported, "required_skills": len(required_skills)}
        
        return score
    
    def _generate_reason(self, provider: IProvider, score: SelectionScore, required_skills: List[str]) -> str:
        """Generate human-readable reason for selection."""
        supported = sum(1 for s in required_skills if provider.supports_skill(s))
        return f"Supports {supported}/{len(required_skills)} required skills. Score: {score.total:.0%}"
