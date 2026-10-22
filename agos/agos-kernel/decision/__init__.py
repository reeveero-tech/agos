"""Decision Engine."""
from dataclasses import dataclass
from typing import List, Optional

from typing import Any

from context import ExecutionContext
from interfaces import ICapability, IProvider
from registry.capability import CapabilityRegistry
from registry.provider import ProviderRegistry
from shared import Result, ResultStatus


@dataclass
class Decision:
    """A decision made by the engine — carries its evidence record."""
    capability: str
    provider: str
    skills: List[str]
    #: عقد الدليل من المسار الموحد (R-W1-004) — كيف اختير الموفّر
    record: Any = None


class DecisionEngine:
    """
    Decides which capability and provider to use.
    Simple rule-based for now.
    """
    
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        provider_registry: ProviderRegistry
    ):
        self.capability_registry = capability_registry
        self.provider_registry = provider_registry
    
    def decide(self, context: ExecutionContext) -> Result[Decision]:
        """
        Make decisions for the mission.

        R-W1-004: الاختيار من المسار الموحد (``DecisionCore``) بسياسة
        هذه الواجهة المعلنة (أول موفّر يدعم مهارة) — والدليل في ``record``.
        
        Rules:
        1. Find requested capability
        2. Find provider that supports required skills (first match wins)
        3. Return decision
        """
        import uuid as _uuid
        from datetime import datetime, timezone
        from decision_pipeline import (DECISION_CORE, DecisionCandidate,
                                        DecisionRequest, FIRST_PROVIDER_POLICY)
        capability_name = context.mission.capability
        
        # Check capability exists
        capability = self.capability_registry.get(capability_name)
        if capability is None:
            return Result(
                status=ResultStatus.FAILURE,
                error=f"Capability not found: {capability_name}",
                record=None
            )
        
        # Get skills needed
        skills = list(capability.skills)
        
        # Find provider for skills — عبر المسار الموحد (نفس القاعدة:
        # أول موفّر يدعم مهارة، بترتيب التسجيل)
        # استعلام مؤجل بحدود المحرك الأصلي: لا بناء مسبق، ولا قراءة
        # أولوية (سياسته المعلنة لا تستهلكها أصلاً) — القلب يستعلم مهارةً
        # مهارةً بترتيب القاعدة ويوقف عند أول دعم، ففشل استعلام مهارة
        # لاحقة لا يحدث أصلاً ما دامت الأولى حسمت الاختيار
        candidates = [DecisionCandidate(
            name=provider.name,
            skill_query=provider.supports_skill,
            ref=provider)
            for provider in self.provider_registry.list_all()]
        record = DECISION_CORE.evaluate(
            DecisionRequest(kind="provider", requested_name="",
                            required_skills=skills, constraints=[]),
            candidates, FIRST_PROVIDER_POLICY,
            decision_id=f"first-{_uuid.uuid4()}",
            timestamp=datetime.now(timezone.utc).isoformat())
        provider = (next(c.ref for c in candidates
                         if c.name == record.selected)
                    if record.status == "selected" else None)
        
        if provider is None:
            # الدليل متاح في الفشل — لا يُسقط (R-W1-004). خطأ البناء
            # المسمّى ظاهر في رسالة التعذر — والرسالة القديمة لحالة
            # عدم المطابقة الحقيقية فقط
            error = (record.errors[0] if record.status == "error" and
                     record.errors else
                     f"No provider found for skills: {skills}")
            return Result(
                status=ResultStatus.FAILURE,
                error=error,
                record=record
            )
        
        # Make decision
        decision = Decision(
            capability=capability_name,
            provider=provider.name,
            skills=skills,
            record=record
        )
        
        # Update context
        context.selected_capability = decision.capability
        context.selected_provider = decision.provider
        context.selected_skills = decision.skills
        
        return Result(
            status=ResultStatus.SUCCESS,
            data=decision
        )
