"""AGOS Architecture Freeze v1.0."""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


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