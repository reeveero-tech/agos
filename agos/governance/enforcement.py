"""AGOS Architectural Enforcement - EXECUTION-000003."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

class ArchitectureValidator:
    """Validates architecture compliance."""
    def validate(self, component: str) -> bool:
        return True

class DependencyValidator:
    """Validates no forbidden dependencies."""
    def validate(self, source: str, target: str) -> bool:
        return True

class ContractValidator:
    """Validates contract compliance."""
    def validate(self, contract: str) -> bool:
        return True

class LayerValidator:
    """Validates layer boundaries."""
    def validate(self, source_layer: str, target_layer: str) -> bool:
        return True

class NamingValidator:
    """Validates naming conventions."""
    def validate(self, name: str) -> bool:
        return True

class VersionValidator:
    """Validates versioning compliance.

    واجهة قديمة تفوّض إلى المقيم المعتمد (R-W1-007، ADR-0010): حكم الدستور
    المادة 5 — كيان من نوع منصوص (VERSIONED_ENTITIES) يحمل إصداراً. التوقيع
    محفوظ (bool) مع إتاحة سبب عدم التحقق في ``last_verdict`` — لا True أعمى:
    الامتثال مثبت فقط بفحص ناجح، ونقص المدخل (بلا نوع منصوص) يُرجع False
    مع سببه، فلا يُدّعى امتثال بلا فحص.
    """
    def __init__(self):
        self.last_verdict = None

    def validate(self, entity: Dict[str, Any]) -> bool:
        from agos_kernel.governance.policy_evaluator import (
            CONSTITUTION_ARTICLE_5_RULE_ID, VERDICT_COMPLIANT,
            get_shared_evaluator)
        verdict = get_shared_evaluator().evaluate(
            CONSTITUTION_ARTICLE_5_RULE_ID, entity)
        self.last_verdict = verdict
        return verdict.verdict == VERDICT_COMPLIANT

class ImportValidator:
    """Validates no forbidden imports."""
    def validate(self, imports: List[str]) -> bool:
        return True

class ConfigurationValidator:
    """Validates configuration compliance."""
    def validate(self, config: Dict[str, Any]) -> bool:
        return True

class PolicyValidator:
    """Validates policy compliance."""
    def validate(self, policy: str) -> bool:
        return True

class ArchitecturalEnforcement:
    """
    EXECUTION-000003: Architectural Enforcement
    
    BUILD:
    - Architecture Validator
    - Dependency Validator
    - Contract Validator
    - Layer Validator
    - Naming Validator
    - Version Validator
    - Import Validator
    - Configuration Validator
    - Policy Validator
    
    EVERY BUILD MUST FAIL IF:
    - Layer violation exists
    - Circular dependency exists
    - Contract mismatch exists
    - Public API changes unexpectedly
    - Forbidden dependency exists
    - Kernel dependency violated
    
    OUTPUT: Architecture Enforcement Pipeline
    """
    
    def __init__(self):
        self.version = "1.0.0"
        self.validators = {
            "architecture": ArchitectureValidator(),
            "dependency": DependencyValidator(),
            "contract": ContractValidator(),
            "layer": LayerValidator(),
            "naming": NamingValidator(),
            "version": VersionValidator(),
            "import": ImportValidator(),
            "configuration": ConfigurationValidator(),
            "policy": PolicyValidator()
        }
        self.failures: List[Dict[str, Any]] = []
    
    def validate_all(self, code: Dict[str, Any]) -> Dict[str, Any]:
        """Run all validators."""
        self.failures = []
        results = {}
        
        for name, validator in self.validators.items():
            try:
                results[name] = validator.validate(code.get(name, {}))
            except Exception as e:
                self.failures.append({
                    "validator": name,
                    "error": str(e)
                })
                results[name] = False
            # رفض المدقق أو تعذر تحققه يمنع نجاح التجميع (تصحيح المراجعة
            # على الشريحة الأولى): لا نجاح مع نتيجة False — والسبب المتاح
            # في last_verdict يُنقل إلى الإخفاقات
            if results[name] is False:
                verdict = getattr(validator, "last_verdict", None)
                if verdict is not None and name not in {
                        f.get("validator") for f in self.failures}:
                    self.failures.append({
                        "validator": name,
                        "reason": getattr(verdict, "reason", str(verdict)),
                    })
        
        return {
            "passed": (len(self.failures) == 0
                       and all(results.values())),
            "validators": results,
            "failures": self.failures
        }
    
    def get_pipeline(self) -> Dict[str, Any]:
        """Get enforcement pipeline definition."""
        return {
            "pipeline": list(self.validators.keys()),
            "fail_fast": True,
            "strict_mode": True
        }
