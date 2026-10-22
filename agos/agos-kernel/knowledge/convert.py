#!/usr/bin/env python3
"""مساعدات التحويل المشتركة للأدلة — R-W1-005 / ADR-0002.

تُستعمل من كل الأسر (kernel/civilization/fabric) كي لا يتكرر منطق التحويل
فيتضارب. سياسة الصدق:
- زمن جمع الدليل (`collected_at`): القيمة الصحيحة تُحفظ كما هي؛ والمفقود
  يبقى `None` (مجهول معلن) — **لا يُختلق `now()`**؛ والقيمة غير القابلة
  للتحليل تحفظ خاماً في `metadata["collected_at_raw"]` ويعلن الزمن مجهولاً.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .models import Evidence, EvidenceQuality


def evidence_dict_to_canonical(ev: Dict[str, Any], owner_id: str, index: int) -> Evidence:
    """دليل قاموسي (أي أسرة) → دليل معتمد كامل الحقول — بلا فقد ولا اختلاق."""
    quality = EvidenceQuality.MEDIUM
    if ev.get("quality"):
        try:
            quality = EvidenceQuality(str(ev["quality"]))
        except ValueError:
            quality = EvidenceQuality.MEDIUM
    collected_at = None
    raw_collected = ev.get("collected_at")
    extra_meta: Dict[str, Any] = dict(ev.get("metadata", {}) or {})
    if isinstance(raw_collected, datetime):
        collected_at = raw_collected
    elif raw_collected is not None:
        # قيمة نصية قابلة للتحليل → تُحل؛ وأي قيمة أخرى (نص فاسد/رقم/غيره)
        # تُحفظ خاماً في collected_at_raw ويُعلن الزمن مجهولاً — لا فقد صامت ولا اختلاق
        parsed = None
        if isinstance(raw_collected, str) and raw_collected.strip():
            try:
                parsed = datetime.fromisoformat(raw_collected)
            except ValueError:
                parsed = None
        if parsed is not None:
            collected_at = parsed
        else:
            extra_meta["collected_at_raw"] = raw_collected
    return Evidence(
        id=str(ev.get("id") or f"{owner_id}-ev-{index}"),
        content=str(ev.get("content", "")),
        source=str(ev.get("source", "")),
        source_url=str(ev.get("source_url", "") or ""),
        quality=quality,
        collected_at=collected_at,
        verified=bool(ev.get("verified", False)),
        verified_by=str(ev.get("verified_by", "") or ""),
        metadata=extra_meta,
    )


def evidence_canonical_to_dict(ev: Evidence) -> Dict[str, Any]:
    """دليل معتمد → قاموس كامل الحقول المعلنة — بلا فقد صامت."""
    out: Dict[str, Any] = {
        "id": ev.id,
        "content": ev.content,
        "source": ev.source,
        "source_url": ev.source_url,
        "quality": ev.quality.value,
        "collected_at": ev.collected_at.isoformat() if ev.collected_at else None,
        "verified": ev.verified,
        "verified_by": ev.verified_by,
    }
    if ev.metadata:
        out["metadata"] = dict(ev.metadata)
    return out
