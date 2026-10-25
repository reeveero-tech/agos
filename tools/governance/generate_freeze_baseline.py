#!/usr/bin/env python3
"""توليد خط أساس محتوى نطاق التجميد المعتمد (R-W1-007 — سجل العمل 0085).

النطاق المعتمد بقرار المالك (2026-10-25 — «اعتماد مع تصحيح المسار»): تسعة
مكونات كما في اقتراح ADR-0010، مع تصحيح مسار النواة من حزمة التحويل
(`agos/agos-kernel/agos_kernel/` — ملف واحد) إلى الشجرة الفعلية الكاملة
(`agos/agos-kernel/` — 441 ملفاً وقت الاعتماد)؛ فبصمة النواة تغطي مسؤولياتها
الفعلية لا الغلاف وحده.

التوليد أداة إنشاء لا مسار تحقق: الخط المعتَمد يُلتزم ملفاً متعقبًا
(docs/architecture/freeze_content_baseline.json) ولا يُولد وقت التحقق؛ وكل
تعديل لاحق في ملفات النطاق يتطلب إعادة توليد الخط في الالتزام نفسه
(عملية حوكمة موثقة) وإلا كسر اختبار الإنفاذ.

الاستخدام: uv run python tools/governance/generate_freeze_baseline.py
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "agos" / "agos-kernel"))

from architecture.freeze import (  # noqa: E402
    FREEZE_CONTENT_BASELINE_DIR,
    FREEZE_CONTENT_BASELINE_FILENAME,
    build_freeze_content_baseline,
    verify_freeze_content,
)

ADOPTED_SCOPE = {
    "kernel": ["agos/agos-kernel/"],
    "core_runtime": ["agos/agos-kernel/runtime/", "agos/agos-kernel/core/"],
    "execution_contracts": [
        "agos/agos-kernel/contracts/", "agos/agos-kernel/contract_engine/"],
    "knowledge_ontology": ["agos/agos-kernel/knowledge/models.py"],
    "policy_ontology": [
        "agos/agos-kernel/governance/policy_evaluator.py",
        "agos/agos-kernel/policies/"],
    "artifact_ontology": ["agos/agos-kernel/runtime/artifact/models.py"],
    "public_apis": ["agos/agos-kernel/api/"],
    "sdk_contracts": ["agos/agos-kernel/sdk/", "agos/agos-kernel/sdks/"],
    "event_model": [
        "agos/agos-kernel/events/", "agos/agos-kernel/event_engine/",
        "agos/agos-kernel/event-engine/"],
}


def main() -> int:
    baseline = build_freeze_content_baseline(REPO_ROOT, ADOPTED_SCOPE)
    out = (REPO_ROOT / FREEZE_CONTENT_BASELINE_DIR
           / FREEZE_CONTENT_BASELINE_FILENAME)
    out.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"خط الأساس مكتوب: {out}")
    for component, data in sorted(baseline["components"].items()):
        print(f"  {component}: {len(data['files'])} ملفاً")
    print(f"البصمة الكلية: {baseline['fingerprint']}")
    report = verify_freeze_content(REPO_ROOT)
    if report["verified"]:
        print(f"التحقق: مطابقة كاملة — {report['files_checked']} فحصاً")
        return 0
    print(f"التحقق: غير مطابق — {report['reason']}")
    for finding in report["findings"]:
        if finding["kind"] != "match":
            print(f"  {finding['kind']}: {finding['path']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
