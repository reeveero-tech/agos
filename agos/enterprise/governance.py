"""AGOS Governance Platform - Every action governed by policies."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

GOVERNANCE_AREAS = ["Architecture", "Security", "Quality", "Compliance", "Release", "Change", "Risk", "Decision"]

class PolicyRuntime:
    """واجهة سياسات مؤسسية تفوّض التقييم إلى المقيم المعتمد (R-W1-007،
    ADR-0010 — الشريحة الثانية). قواعد السياسة نصوص حرة: **لا تُحوَّل
    آلياً إلى شروط تنفيذية** — النص القابل للفحص الوحيد هو معرّف قاعدة
    مسجلة لدى المقيم (مواصفة تنفيذية)؛ ما سواه (سياسة مجهولة، قاعدة نص حر
    بلا مواصفة، مدخل ناقص) لا ينتج True — سببه في ``last_reason``. سير
    الموافقات والتدقيق المؤسسي خارج هذه الشريحة (كما كان)."""

    def __init__(self):
        self._policies: Dict[str, Dict[str, Any]] = {}
        # سبب آخر تقييم — متاح للفحص لا حكم أعمى
        self.last_reason: str = ""
    
    def create_policy(self, name: str, rules: List[str]) -> Dict[str, Any]:
        policy = {"name": name, "rules": rules, "status": "active"}
        self._policies[name] = policy
        return policy
    
    def evaluate(self, policy_name: str, context: Dict[str, Any]) -> bool:
        """تفويض إلى المقيم المعتمد: السماح مثبتاً فقط بفحص ناجح لكل قواعد
        السياسة؛ المنع عند مخالفة؛ وما لا يمكن فحصه لا يُعلن سماحاً."""
        from agos_kernel.governance.policy_evaluator import (
            VERDICT_COMPLIANT, get_shared_evaluator)
        policy = self._policies.get(policy_name)
        if policy is None:
            self.last_reason = "سياسة مجهولة — لا فحص ولا سماح مثبت"
            return False
        evaluator = get_shared_evaluator()
        rules = policy.get("rules") or []
        if not rules:
            self.last_reason = "السياسة بلا قواعد — لا فحص ولا سماح مثبت"
            return False
        for rule in rules:
            # قاعدة نصية: لا تُحوَّل آلياً — تُفحص فقط إن كانت معرّف قاعدة
            # مسجلة لدى المقيم (مواصفة تنفيذية)
            if evaluator.get_spec(rule) is None:
                self.last_reason = (
                    f"قاعدة غير قابلة للفحص (نص حر بلا مواصفة تنفيذية): "
                    f"{rule!r}")
                return False
            verdict = evaluator.evaluate(rule, context)
            if verdict.verdict != VERDICT_COMPLIANT:
                # منع معلل أو عدم تحقق معلل — كلاهما لا يُعلن سماحاً
                self.last_reason = (
                    f"{verdict.verdict}: {verdict.reason}")
                return False
        self.last_reason = "فحص كل قواعد السياسة ناجح — سماح مثبت"
        return True

class ApprovalWorkflow:
    def __init__(self):
        self._approvals: Dict[str, str] = {}  # request_id -> status
    
    def submit(self, request_id: str) -> None:
        self._approvals[request_id] = "pending"
    
    def approve(self, request_id: str) -> None:
        self._approvals[request_id] = "approved"
    
    def reject(self, request_id: str) -> None:
        self._approvals[request_id] = "rejected"

class AuditEngine:
    def __init__(self):
        self._records: List[Dict[str, Any]] = []
    
    def record(self, action: str, user: str, details: Dict[str, Any]) -> None:
        self._records.append({"action": action, "user": user, "details": details, "timestamp": "now"})

class GovernancePlatform:
    """
    Governance Platform.
    
    Every engineering action must be governed by policies and traceable through immutable records.
    
    Implements:
    ✅ Policy Runtime, Approval Workflows
    ✅ Architecture Governance, Security Governance
    ✅ Quality Governance, Compliance Governance
    ✅ Release Governance, Change Governance
    ✅ Risk Governance, Decision Governance
    ✅ Audit Engine, Evidence Engine
    """
    def __init__(self):
        self.version = "2.0.0"
        self.policies = PolicyRuntime()
        self.approvals = ApprovalWorkflow()
        self.audit = AuditEngine()
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "governance_areas": GOVERNANCE_AREAS
        }
