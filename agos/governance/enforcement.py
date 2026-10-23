"""AGOS Architectural Enforcement - EXECUTION-000003."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

class _UnspecValidator:
    """قاعدة مشتركة للمصادقات بلا مواصفة مسجلة (R-W1-007 — الشريحة الخامسة).

    لا True أعمى: حكم ``unverified`` معلل عبر المقيم المعتمد بغياب المواصفة
    التنفيذية لنوع الحكم — والإرجاع ``False`` بمعنى **عدم ثبوت الامتثال**
    لا مخالفة مثبتة. لا تُسجل مواصفات صورية ولا تُستنتج قواعد من نص حر:
    عند تسجيل مواصفة حقيقية لهذا النوع يصبح الفحص ممكناً عبر المسار نفسه.
    ``RULE_ID`` معرّف نوع الحكم — يبقى بلا مواصفة عمداً حتى يُعرَّف فحصه.
    """

    RULE_ID = ""

    def __init__(self):
        self.last_verdict = None

    def _evaluate_unspec(self, entity: Dict[str, Any]) -> bool:
        from agos_kernel.governance.policy_evaluator import (
            get_shared_evaluator)
        # مسار عدم التحقق في المقيم المشترك: معرّف بلا مواصفة ⇒ unverified
        # معلل — السبب متاح في last_verdict لنقله إلى إخفاقات التجميع
        self.last_verdict = get_shared_evaluator().evaluate(
            self.RULE_ID, entity)
        return self.last_verdict.compliant_proven


class ArchitectureValidator(_UnspecValidator):
    """Validates architecture compliance — بلا مواصفة مسجلة: حكم unverified
    معلل لا True أعمى (الامتثال غير مثبت — لا يُدَّعى فحص معماري)."""
    RULE_ID = "enforcement-architecture-validation"

    def validate(self, component: str) -> bool:
        return self._evaluate_unspec({"component": component})

class DependencyValidator(_UnspecValidator):
    """Validates no forbidden dependencies — لا مواصفة مسجلة لهذا الفحص
    في المقيم المعتمد: unverified معلل (غياب المواصفة المثبت بالحصر، لا
    الحكم على غياب القواعد من المشروع كله)."""
    RULE_ID = "enforcement-dependency-validation"

    def validate(self, source: str, target: str) -> bool:
        return self._evaluate_unspec({"source": source, "target": target})

class ContractValidator(_UnspecValidator):
    """Validates contract compliance — بلا مواصفة مسجلة: unverified معلل."""
    RULE_ID = "enforcement-contract-validation"

    def validate(self, contract: str) -> bool:
        return self._evaluate_unspec({"contract": contract})

class LayerValidator(_UnspecValidator):
    """Validates layer boundaries — لا مواصفة مسجلة لهذا الفحص في المقيم
    المعتمد: unverified معلل (غياب المواصفة المثبت بالحصر)."""
    RULE_ID = "enforcement-layer-validation"

    def validate(self, source_layer: str, target_layer: str) -> bool:
        return self._evaluate_unspec({"source_layer": source_layer,
                                      "target_layer": target_layer})

class NamingValidator(_UnspecValidator):
    """Validates naming conventions — لا مواصفة مسجلة لهذا الفحص في المقيم
    المعتمد: unverified معلل (غياب المواصفة المثبت بالحصر)."""
    RULE_ID = "enforcement-naming-validation"

    def validate(self, name: str) -> bool:
        return self._evaluate_unspec({"name": name})

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

class ImportValidator(_UnspecValidator):
    """Validates no forbidden imports — لا مواصفة مسجلة لهذا الفحص في
    المقيم المعتمد: unverified معلل (غياب المواصفة المثبت بالحصر)."""
    RULE_ID = "enforcement-import-validation"

    def validate(self, imports: List[str]) -> bool:
        return self._evaluate_unspec({"imports": imports})

class ConfigurationValidator(_UnspecValidator):
    """Validates configuration compliance — بلا مواصفة مسجلة: unverified
    معلل."""
    RULE_ID = "enforcement-configuration-validation"

    def validate(self, config: Dict[str, Any]) -> bool:
        return self._evaluate_unspec({"config": config})

class PolicyValidator(_UnspecValidator):
    """Validates policy compliance — بلا مواصفة مسجلة: unverified معلل
    (النص الحر لا يُحوَّل آلياً إلى شرط تنفيذي)."""
    RULE_ID = "enforcement-policy-validation"

    def validate(self, policy: str) -> bool:
        return self._evaluate_unspec({"policy": policy})

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
        
        # توثيق حمولات المصادقتين ثنائيتي الوسيطين (تصحيح المراجعة — الشريحة
        # الخامسة): حمولتهما قاموس بحقول مسماة بأسماء وسائطهما — تنقصها
        # يُعرض كعدم تحقق معلل (المصادقة تُستدعى بلا قيمة مختلقة) لا كخطأ
        # عدد وسائط مخفي: كان المجمّع يمرر وسيطاً واحداً لتواقيع تطلب اثنين
        _TWO_ARG_FIELDS = {
            "dependency": ("source", "target"),
            "layer": ("source_layer", "target_layer"),
        }
        for name, validator in self.validators.items():
            try:
                payload = code.get(name, {})
                if name in _TWO_ARG_FIELDS:
                    fields = payload if isinstance(payload, dict) else {}
                    first, second = _TWO_ARG_FIELDS[name]
                    results[name] = validator.validate(
                        fields.get(first), fields.get(second))
                else:
                    results[name] = validator.validate(payload)
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
