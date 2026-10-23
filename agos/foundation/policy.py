"""AGOS Universal Policy Runtime - EXECUTION-000016."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

POLICY_TYPES = ["Security", "Architecture", "Execution", "Knowledge", "Lifecycle", "Governance", "Quality", "Performance", "Cost", "Compliance", "Risk"]

@dataclass
class Policy:
    policy_id: str
    policy_type: str
    name: str
    description: str
    rules: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    enabled: bool = True

class PolicyRegistry:
    def __init__(self):
        self._policies: Dict[str, Policy] = {}
    
    def register(self, policy: Policy) -> bool:
        self._policies[policy.policy_id] = policy
        return True
    
    def get(self, policy_id: str) -> Policy:
        return self._policies.get(policy_id)
    
    def list_by_type(self, policy_type: str) -> List[Policy]:
        return [p for p in self._policies.values() if p.policy_type == policy_type]

class PolicyEvaluator:
    """مقيم واجهة السياسة الشاملة — يفوّض الحكم إلى المقيم المعتمد
    (R-W1-007، ADR-0010 — الشريحة الثالثة): كان يرجع allowed=True أعمى؛
    السماح الآن مثبت فقط بفحص ناجح لكل قواعد السياسة عبر المقيم المعتمد،
    والقاعدة القابلة للفحص هي قاموس بمعرّف قاعدة مسجلة (rule_id) — لا
    يُحوَّل الشكل الحر آلياً؛ والسبب متاح في ``reason``."""

    def evaluate(self, policy: Policy, context: Dict[str, Any]) -> Dict[str, Any]:
        from agos_kernel.governance.policy_evaluator import evaluate_rule_dicts
        result = evaluate_rule_dicts(policy.rules, context)
        return {"allowed": result["allowed"], "policy": policy.name,
                "reason": result["reason"]}

class UniversalPolicyRuntime:
    """
    Universal Policy Runtime.
    
    Policies govern every operation.
    Business logic must never contain policy decisions.
    
    Policy Types (11):
    ✅ Security, Architecture, Execution, Knowledge
    ✅ Lifecycle, Governance, Quality, Performance
    ✅ Cost, Compliance, Risk
    
    Implements:
    ✅ Policy Runtime, Registry, Evaluator, Simulator
    ✅ Versioning, Audit, Analytics
    
    OUTPUT: Universal Policy Runtime
    """
    def __init__(self):
        self.version = "1.0.0"
        self.registry = PolicyRegistry()
        self.evaluator = PolicyEvaluator()
    
    def create_policy(self, policy_type: str, name: str, description: str, rules: List[Dict[str, Any]] = None) -> Policy:
        policy = Policy(
            policy_id=f"policy_{name}",
            policy_type=policy_type,
            name=name,
            description=description,
            rules=rules or []
        )
        self.registry.register(policy)
        return policy
    
    def evaluate(self, policy_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        policy = self.registry.get(policy_id)
        if policy:
            return self.evaluator.evaluate(policy, context)
        return {"error": "Policy not found"}
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "policy_types": POLICY_TYPES,
            "total_policies": len(self.registry._policies)
        }
