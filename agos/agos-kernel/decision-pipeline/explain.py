"""شرح القرار — الجواب على «لماذا X؟» من الدليل المسجل وحده (R-W2-010).

المادة 12 (الدستور، ``DECISION_REQUIREMENTS``): كل قرار
Traceable/Explainable/Repeatable/Auditable — وهذا المفسر ينفذها سلوكياً:
- التتبع: كل تعليل مربوط بحقول محددة في السجل ولقطة السياسة المسجلة.
- التفسير: يبين السبب الفعلي للحسم — حسابي أو خروج مبكر أو أهلية —
  لا حكاية موحدة تُلصق بكل قرار.
- التكرار: المفسر يعمل من السجل المحفوظ وحده بلا استعلامات خارجية
  ولا مرشحين أحياء ولا إعادة تطبيق قواعد؛ فسجل JSON المحفوظ يعطي
  التفسير نفسه دائماً، والدرجة قابلة لإعادة الحساب من لقطة السياسة
  والقيم المسجلة.
- التدقيق: يشمل المرشحين والنقص والأخطاء — لا الفائز وحده.

حدود الأمانة التفسيرية (من ADR-0006 ومراجعات R-W1-004):
- لا تُدّعى قاعدة منفردة «سببت الفوز» — فرق الدرجات يُعرض فقط حيث
  المقارنة الحسابية صالحة (القيمتان مقررتان، والمساهمة غير ثابتة).
- المستبعد بالأهلية لم يدخل المنافسة أصلاً — لا يُوصف بخسارة درجة.
- قاعدة الخروج المبكر تُشرح بقيادتها الفعلية (المهارة الحاسمة وترتيب
  التسجيل وحدود توقف الاستعلام) لا بمفاضلة درجات مختلقة.
- القيود مساهمة افتراضية معلنة — لا توصف أبداً بأنها «اجتازت فحصاً».
- السجل الناقص أو القاعدة غير المفهومة ينتج نقصاً مسمّى (``gaps``)
  لا شرحاً مطمئناً.
- مسار ``caller-provided`` (``cognitive.decision``) خارج هذا المفسر:
  تقديره من مستدعيه وموسوم بصدقه — لا يصير قراراً مثبتاً بالتغليف.

المفسر لا يستدعي ``to_dict`` (لا استدعاء دائري عند الربط بالمخرجات).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

#: فرق درجات تحت هذا الحد يُعد تعادلاً حقيقياً (كما في فرز القلب)
_EPS = 1e-12


def _rules(record: Any) -> Dict[str, Any]:
    snapshot = getattr(record, "policy_snapshot", None) or {}
    return dict(snapshot.get("rules", {}))


def _eval_by_name(record: Any) -> Dict[str, Any]:
    return {c.name: c for c in record.candidates}


def _ranking_missing(record: Any) -> List[str]:
    """منافسون مؤهلون اكتمل تقييمهم غائبون من الترتيب — أسماؤهم.

    الفحص بالغياب لا بفراغ القائمة: ترتيب [selected] وحده مع منافس مؤهل
    غائب منه نقص مكشوف — كما يكون حذف الترتيب كله.
    """
    if getattr(record, "selected", None) is None:
        return []
    ranked = list(getattr(record, "ranked_alternatives", []) or [])
    return [c.name for c in getattr(record, "candidates", [])
            if c.name != record.selected
            and not c.excluded and not c.build_failed
            and _completed_evaluation(c)
            and c.name not in ranked]


def _unsupported_rule(rules: Dict[str, Any]) -> Optional[tuple]:
    """أول قاعدة حاسمة موجودة بقيمة غير مدعومة — (المفتاح، القيمة)."""
    for key in _MECHANISM_RULE_VALUES:
        if key in rules and not _value_known(rules, key):
            return key, rules[key]
    return None


def _selected_eval(record: Any) -> Optional[Any]:
    by_name = _eval_by_name(record)
    return by_name.get(record.selected) if record.selected else None


#: مفاتيح القواعد المعروفة في السياسات المعلنة — ما عداها لا يثبت آلية
_KNOWN_RULE_KEYS = ("capability_scoring", "provider_stages", "eligibility",
                   "tie_break", "name_match", "exclusion",
                   "priority_contribution", "constraint_contribution",
                   "selection")

#: مفاتيح تحدد الآلية فعلاً — قيمتها يجب أن تكون معروفة، لا المفتاح وحده:
#: مفتاح معروف بقيمة مجهولة = آلية مجهولة (نقص مسمّى لا تعليل مطمئن)
_MECHANISM_RULE_VALUES = {
    "capability_scoring": ("jaccard-exact-override",),
    "provider_stages": ("filter-then-evaluate",),
    "eligibility": ("exact-name-if-available", "supports-all-if-available"),
    "selection": ("first-in-registration-order-supporting-a-skill",),
    "exclusion": ("no-name-or-skill-relationship",
                  "no-required-skill-support"),
    "tie_break": ("stable-registration-order",
                  "first-required-skill-then-registration-order"),
    "priority_contribution": ("constant-1.0", "unused"),
    "constraint_contribution": ("declared-default-not-evaluated",),
}

#: أسباب الاستبعاد بالأهلية الشرطية (تقيد المنافسة فعلاً) — غيرها استبعاد
#: عدم علاقة/عدم دعم ولا يُدّعى به قيد أهلية
_CONDITIONAL_ELIGIBILITY = (
    "not-an-exact-name-match-while-exact-available",
    "does-not-support-all-required-while-full-support-exists",
)


def _completed_evaluation(cand: Any) -> bool:
    """اكتمل تقييم هذا المرشح فعلاً؟ — من الدليل لا من غياب الوسم.

    غياب build_failed وexcluded لا يثبت التقييم: مرشح الاستعلام المؤجل
    قد يكون «لم يُستعلم أصلاً» (توقف القرار قبله). الدليل على الاكتمال:
    درجة مسجلة أو حالة حسم مسجلة.
    """
    if cand is None:
        return False
    if cand.score is not None:
        return True
    return cand.values_used.get("query_state") == "decided"


def _mechanism(record: Any) -> str:
    """آلية الحسم الفعلية كما سجلتها السياسة والحقول — لا تخمين.

    - ``early-exit-first-supporting``: قاعدة المحرك القديم — أول دعم
      يفوز ويوقف الاستعلام (أو يرتب بأول مهارة مدعومة)، لا مفاضلة درجات.
    - ``computational-staged``: مسار الدُبعة للموفّرين — مرحلتا فحص
      ثم تقييم داخل القلب.
    - ``computational``: مفاضلة حسابية معلنة الأوزان.
    - ``unknown``: لا دليل يثبت الآلية — نقص مسمّى لا افتراض.
    """
    rules = _rules(record)
    # أي قاعدة حاسمة موجودة بقيمة غير مدعومة تعلن الآلية مجهولة — قبل
    # كل مخارج التحديد (حتى selection وprovider_stages): لا تعليل مطمئن
    # لقاعدة لا يفهمها المفسر مهما كانت بقية القواعد سليمة
    for key in _MECHANISM_RULE_VALUES:
        if key in rules and not _value_known(rules, key):
            return "unknown"
    selection = rules.get("selection")
    if selection is not None:
        if selection == "first-in-registration-order-supporting-a-skill":
            return "early-exit-first-supporting"
        # قاعدة اختيار مسجلة غير معروفة — لا يُفترض لها مسار حسابي
        return "unknown"
    if getattr(record, "tie_break", "") == \
            "first-required-skill-then-registration-order":
        return "early-exit-first-supporting"
    if rules.get("provider_stages") == "filter-then-evaluate":
        return "computational-staged"
    # المفاضلة الحسابية تثبت بمفاتيح قواعد معروفة فعلاً وبقيمها المعروفة
    # — لا يكفي وجود المفتاح: مفتاح معروف بقيمة مجهولة آلية مجهولة.
    # والمفاتيح الزخرفية (تعريفات لا آليات) لا تثبت شيئاً وحدها
    if any(_value_known(rules, k) for k in _MECHANISM_RULE_VALUES) \
            or getattr(record, "tie_break", ""):
        return "computational"
    return "unknown"


def _value_known(rules: Dict[str, Any], key: str) -> bool:
    """المفتاح موجود وبقيمة معروفة — لا المفتاح وحده."""
    if key not in rules:
        return False
    value = rules[key]
    if key == "name_match":
        # سلّم الأسماء قاموس بمفاتيح معروفة
        return isinstance(value, dict) and bool(value)
    return value in _MECHANISM_RULE_VALUES[key]


def explain_decision(record: Any) -> Dict[str, Any]:
    """الجواب على «لماذا X؟» — من حقول السجل وحده، بلا استعلامات.

    الدخل أي كائن له حقول :class:`DecisionRecord`؛ المخرج قاموس قابل
    للتسلسل JSON يظهر تلقائياً في ``to_dict`` السجل (مفتاح ``why``).
    """
    out: Dict[str, Any] = {
        "decision_id": getattr(record, "decision_id", ""),
        "kind": getattr(record, "kind", ""),
        "status": getattr(record, "status", "no_match"),
        "policy": {
            "policy_id": getattr(record, "policy_id", ""),
            "policy_version": getattr(record, "policy_version", ""),
        },
        "decision_type": "",
        "answer": "",
        "why": {},
        "alternatives": [],
        "missing_info": list(getattr(record, "missing_info", []) or []),
        "errors": list(getattr(record, "errors", []) or []),
        "gaps": [],
        # التتبع: روابط التعليل بحقول السجل ولقطة السياسة المسجلة
        "trace": {
            "policy_id": getattr(record, "policy_id", ""),
            "policy_version": getattr(record, "policy_version", ""),
            "tie_break": getattr(record, "tie_break", ""),
            "timestamp": getattr(record, "timestamp", ""),
            "from_record_only": True,
        },
    }
    status = out["status"]
    if status == "selected" and getattr(record, "selected", None):
        _explain_selected(record, out)
    elif status == "error":
        _explain_error(record, out)
    else:
        _explain_no_match(record, out)
    _explain_gaps(record, out)
    return out


# ---------------------------------------------------------------------------
# الاختيار — لماذا X تحديداً؟
# ---------------------------------------------------------------------------

def _explain_selected(record: Any, out: Dict[str, Any]) -> None:
    mechanism = _mechanism(record)
    out["decision_type"] = mechanism
    selected_ev = _selected_eval(record)
    if selected_ev is None:
        out["gaps"].append("selected-candidate-evidence-missing")
        out["answer"] = (f"اختير {record.selected} لكن الدليل لا يحمل "
                         "تقييمه — نقص مسمّى لا تعليل مطمئن")
        return
    if mechanism == "unknown":
        # لا دليل يثبت آلية الحكم — لا يُفترض حساب ولا خروج مبكر.
        # سبب الجهالة مسمّى بدقة: القواعد غير مسجلة أصلاً ≠ قاعدة
        # مسجلة بقيمة غير مدعومة (تُسمّى بمفتاحها وقيمتها) ≠ قواعد
        # مسجلة لا يعرفها المفسر
        rules = _rules(record)
        unsupported = _unsupported_rule(rules)
        if not rules:
            out["gaps"].append("selection-rules-not-recorded")
            out["answer"] = (f"اختير {record.selected} لكن الدليل لا يثبت "
                             "آلية الحسم — لا قواعد مسجلة أصلاً (نقص "
                             "مسمّى لا تعليل مطمئن)")
        elif unsupported is not None:
            key, value = unsupported
            out["gaps"].append(f"unsupported-rule-value: {key}={value}")
            out["answer"] = (
                f"اختير {record.selected} لكن الدليل لا يثبت آلية الحسم: "
                f"قاعدة مسجلة بقيمة غير مدعومة ({key} = {value}) — "
                "المفسر لا يفهمها فلا يعلل بها (نقص مسمّى لا تعليل مطمئن)")
        else:
            out["gaps"].append("selection-rules-unrecognized")
            out["answer"] = (f"اختير {record.selected} لكن الدليل لا يثبت "
                             "آلية الحسم — قواعد مسجلة لا يعرفها "
                             "المفسر (نقص مسمّى لا تعليل مطمئن)")
        return
    if mechanism == "early-exit-first-supporting":
        _explain_early_exit(record, out, selected_ev)
    else:
        _explain_computational(record, out, selected_ev)


def _explain_early_exit(record: Any, out: Dict[str, Any],
                        selected_ev: Any) -> None:
    """قاعدة المحرك القديم: أول دعم يفوز — يُشرح بقيادته الفعلية.

    مساران مختلفان في القلب لا يُوصفان بعبارة واحدة:
    - استعلام مؤجل: مهارةً مهارةً وتوقف عند أول دعم — «توقف الاستعلام»
      وصف صادق هنا فقط.
    - مهارات معلنة: ترتيب بأول مهارة مدعومة ثم التسجيل — لا استعلام
      أصلاً، فادعاء التوقف كذب على الدليل.
    """
    required = list((getattr(record, "requested", {}) or {}).get(
        "required_skills", []) or [])
    supported = (selected_ev.values_used.get("supported_skills")
                 or list(selected_ev.offered_skills))
    decisive = next((s for s in required if s in supported), None)
    if decisive is None:
        # مسار الاستعلام المؤجل: المهارة الحاسمة مسجلة في الدليل
        decisive = selected_ev.values_used.get("decided_by_skill")
    lazy = any(c.values_used.get("query_state")
               for c in record.candidates)
    out["why"] = {
        "rule": "first-in-registration-order-supporting-a-skill",
        "decisive_skill": decisive,
        "path": "lazy-queries" if lazy else "declared-skills",
        "selection_mode": "early-exit-no-score-race",
        "selected_support": list(supported),
    }
    if decisive is None:
        out["gaps"].append("decisive-skill-not-recorded")
        out["answer"] = (f"اختير {record.selected}: أول مرشح بترتيب التسجيل "
                         "يدعم مهارة مطلوبة — بلا مفاضلة درجات؛ المهارة "
                         "الحاسمة غير مسجلة في الدليل (نقص مسمّى)")
    elif lazy:
        out["answer"] = (
            f"اختير {record.selected}: أول مرشح بترتيب التسجيل يدعم "
            f"المهارة «{decisive}» — قاعدة الخروج المبكر توقف الاستعلام "
            "عند أول دعم، فلا مفاضلة درجات أصلاً")
    else:
        out["answer"] = (
            f"اختير {record.selected}: أول من يدعم المهارة المطلوبة الأولى "
            f"«{decisive}» — الترتيب بأسبقية المهارة المدعومة في طلب "
            "الطلب ثم ترتيب التسجيل؛ لا استعلام أصلاً (المهارات معلنة) "
            "فلا مفاضلة درجات")
    out["alternatives"] = _early_exit_alternatives(record, selected_ev)


def _early_exit_alternatives(record: Any, selected_ev: Any) -> List[Dict[str, Any]]:
    """لماذا لم يُختر غير المختار — بحالات الاستعلام المسجلة لا بالدرجات."""
    alternatives: List[Dict[str, Any]] = []
    for cand in record.candidates:
        if cand.name == record.selected:
            continue
        entry: Dict[str, Any] = {"name": cand.name}
        state = cand.values_used.get("query_state")
        if cand.build_failed:
            entry["why_not"] = ("تعذر استعلامه/تقييمه — مسجل بموضع فشله "
                                f"({cand.values_used.get('failed_stage', 'evaluation')})")
        elif state == "not_queried":
            entry["why_not"] = ("لم يُستعلم أصلاً: توقف الاستعلام عند "
                                "الحسم قبله (حدود القاعدة)")
        elif state == "queried":
            answers = cand.values_used.get("query_answers", {})
            entry["why_not"] = ("استُعلم وأجاب بعدم دعم ما سُئل عنه "
                                f"({answers})")
        elif state == "decided":
            entry["why_not"] = "حسم الاختيار قبله بترتيب التسجيل"
        elif cand.excluded:
            entry["why_not"] = (f"استُبعد بالأهلية ({cand.exclusion_reason}) "
                                "— لم يدخل المنافسة أصلاً")
        else:
            # مسار المرشحين المعلَنين (غير المؤجل): السبب الفعلي مستخرج
            # من المهارات المعلنة — لا احتمالان بـ«أو» يحجبان السبب
            required = list((getattr(record, "requested", {}) or {}).get(
                "required_skills", []) or [])
            sel_supported = (selected_ev.values_used.get("supported_skills")
                             or list(selected_ev.offered_skills))
            cand_supported = (cand.values_used.get("supported_skills")
                              or list(cand.offered_skills))
            sel_first = next((i for i, s in enumerate(required)
                              if s in sel_supported), len(required))
            cand_first = next((i for i, s in enumerate(required)
                               if s in cand_supported), len(required))
            if cand_first == len(required):
                entry["why_not"] = "لا يدعم أي مهارة مطلوبة"
            elif cand_first == sel_first:
                entry["why_not"] = ("يدعم المهارة الحاسمة نفسها لكنه يلي "
                                    "المختار بترتيب التسجيل")
            else:
                entry["why_not"] = (
                    f"أول مهارة يدعمها («{required[cand_first]}») لاحقة في "
                    f"ترتيب الطلب عن المهارة الحاسمة («{required[sel_first]}»)")
        alternatives.append(entry)
    return alternatives


def _explain_computational(record: Any, out: Dict[str, Any],
                           selected_ev: Any) -> None:
    """المفاضلة الحسابية: القيم والمساهمات والفارق مع أقرب منافس."""
    # فحص الترتيب أولاً — حاجز غير مشروط قبل اشتقاق المنافس والمقارنة
    # والتعادل: فالترتيب الناقص يجعل كل «أقرب منافس» ادعاءً بلا دليل،
    # ولا يجوز تحليل فارق ثم إضافة النقص متأخراً دون تصحيح الجواب
    missing = _ranking_missing(record)
    if missing:
        out["gaps"].append("ranked-alternatives-missing")
        out["why"]["ranking_incomplete"] = {"missing": missing}
        out["answer"] = (
            f"اختير {record.selected} — لكن ترتيب المنافسين ناقص "
            f"(غاب: {', '.join(missing)}): الدليل لا يكفي للمقارنة "
            "الكاملة (نقص مسمّى، لا تعليل مطمئن)")
        out["alternatives"] = _computational_alternatives(
            record, selected_ev)
        return
    rules = _rules(record)
    snapshot = getattr(record, "policy_snapshot", None) or {}
    weights = dict(snapshot.get("weights", {}))
    alternatives_ranked = [n for n in record.ranked_alternatives
                           if n != record.selected]
    runner_name = alternatives_ranked[0] if alternatives_ranked else None
    runner_ev = (_eval_by_name(record).get(runner_name)
                 if runner_name else None)

    why: Dict[str, Any] = {
        "rule": ("jaccard-exact-override" if rules.get(
            "capability_scoring") == "jaccard-exact-override"
            else "highest-total-score"),
        "policy_weights": weights,
        "selected_values": _rule_values(selected_ev),
    }
    # المنافسة قد تكون محصورة بالأهلية الشرطية أصلاً — فإن لم يبقَ منافس
    # مُقيَّم فلا يُدّعى سباق درجات أصلاً؛ يُشرح القيد ثم الاختيار.
    # التصنيف بالسبب المسجل: قيد الأهلية الشرطية ≠ استبعاد عدم العلاقة
    conditional_excluded = [c for c in record.candidates
                            if c.excluded and c.name != record.selected
                            and c.exclusion_reason in _CONDITIONAL_ELIGIBILITY]
    if runner_ev is None and conditional_excluded:
        reasons = {c.name: c.exclusion_reason for c in conditional_excluded}
        why["competition_restricted_by"] = reasons
        out["answer"] = (
            f"اختير {record.selected}: المنافسة محصورة بالأهلية الشرطية "
            f"({'; '.join(sorted(set(reasons.values())))}) — فهو المنافس "
            "المؤهل الوحيد، ولا يُدّعى سباق درجات مع مستبعدين لم تُحسب "
            "درجاتهم أصلاً")
    else:
        out["answer"] = f"اختير {record.selected}: أعلى درجة إجمالية"
    if runner_ev is not None:
        total_sel = _total(selected_ev)
        total_run = _total(runner_ev)
        if total_sel is not None and total_run is not None:
            if total_sel == total_run:
                # تعادل تام في القيمة المسجلة: الحسم بقاعدة كسر التعادل
                # المعلنة — لا بالدرجات؛ وغياب القاعدة نقص لا اختلاق
                why["tie"] = {
                    "selected_total": total_sel, "runner_total": total_run,
                    "resolved_by": record.tie_break or None,
                }
                if record.tie_break:
                    out["answer"] = (
                        f"اختير {record.selected}: تعادل حقيقي في الدرجة "
                        f"({total_sel:.4f}) حُسم بقاعدة كسر التعادل المعلنة "
                        f"«{record.tie_break}» — لا أفضلية درجات")
                else:
                    out["gaps"].append("tie-break-not-recorded")
                    out["answer"] = (
                        f"اختير {record.selected}: تعادل حقيقي في الدرجة "
                        f"({total_sel:.4f}) وقاعدة كسر التعادل غير مسجلة "
                        "في الدليل — نقص مسمّى لا تعليل مطمئن")
            elif abs(total_sel - total_run) < _EPS:
                # فارق دقيق دون عتبة كسر التعادل: القلب يفرز بالدرجة
                # الفعلية (الأعلى أولاً) — لا يُدّعى تعادل حُسم بالتسجيل
                why["near_tie"] = {
                    "selected_total": total_sel, "runner_total": total_run,
                    "note": "فارق دون عتبة كسر التعادل — الحسم بالدرجة "
                            "الفعلية المسجلة لا بترتيب التسجيل",
                    "tie_break_also_recorded": record.tie_break or None,
                }
                out["answer"] = (
                    f"اختير {record.selected}: أعلى درجة فعلاً ولو بفارق "
                    f"دقيق ({total_sel:.13f} مقابل {total_run:.13f}) دون "
                    "عتبة كسر التعادل — الحسم بالدرجة المسجلة لا بترتيب "
                    "التسجيل")
            else:
                # فارق حسابي صالح: يُعرض مع مكوناته — بلا ادعاء أن قاعدة
                # منفردة «سببت» الفوز (المساهمات معلنة الأوزان)
                why["margin"] = {
                    "selected_total": total_sel,
                    "runner": runner_name,
                    "runner_total": total_run,
                    "components": _valid_components(selected_ev, runner_ev,
                                                   rules),
                }
                out["answer"] = (
                    f"اختير {record.selected}: أعلى درجة إجمالية "
                    f"({total_sel:.4f}) متقدماً على أقرب منافس "
                    f"{runner_name} ({total_run:.4f}) — بمكونات الدرجة "
                    "المسجلة وأوزان لقطة السياسة")
        else:
            # دليل المقارنة ناقص: الجواب يصرح — لا يبقى جزم «أعلى درجة»
            # بحاشية (كما عند فقدان إجمالي المختار نفسه)
            out["gaps"].append("runner-up-total-not-comparable")
            out["answer"] = (
                f"الدليل لا يكفي للمقارنة مع {runner_name}: إجماليه غير "
                "قابل للمقارنة في الدليل — نقص مسمّى، لا تعليل مطمئن")
    else:
        # لا يُخترع نقص: مرشح وحيد كافٍ، ومنافسو حُصرت منافستهم بالأهلية
        # أو استُبعدوا ليسوا نقصاً (فحص الغياب الموحد أعلاه حاجز مبكر)
        pass
    if rules.get("priority_contribution") == "constant-1.0":
        why["priority_note"] = ("أولوية الموفّرين مساهمة ثابتة معلنة في "
                                "السياسة (غير مقروءة) — فالفارق الحسابي "
                                "من المهارات وحدها")
    if rules.get("priority_contribution") == "unused":
        why["priority_note"] = "الأولوية غير مستهلكة في هذه القاعدة أصلاً"
    out["why"] = why
    out["alternatives"] = _computational_alternatives(record, selected_ev)


def _computational_alternatives(record: Any,
                                 selected_ev: Any) -> List[Dict[str, Any]]:
    """لماذا لم يُختر غير المختار — مستبعد بالأهلية/فحص/تعادل/درجة/تعذر."""
    alternatives: List[Dict[str, Any]] = []
    selected_total = _total(selected_ev)
    for cand in record.candidates:
        if cand.name == record.selected:
            continue
        entry: Dict[str, Any] = {"name": cand.name}
        if cand.build_failed:
            entry["why_not"] = (
                "تعذر تقييمه — مسجل بموضع فشله "
                f"({cand.values_used.get('failed_stage', 'evaluation')})")
        elif cand.excluded:
            reason = cand.exclusion_reason
            if reason in _CONDITIONAL_ELIGIBILITY:
                entry["why_not"] = (
                    f"استُبعد بالأهلية الشرطية ({reason}) — لم تُحسب درجته "
                    "أصلاً فلا يُدّعى أنه خسر بالدرجة، ولا أن درجة محتملة "
                    "أعلى كانت ستكفي")
            else:
                entry["why_not"] = (f"استُبعد ({reason}) — لا علاقة اسماً "
                                    "ولا مهارات بالطلب")
        else:
            total = _total(cand)
            if (total is not None and selected_total is not None
                    and total == selected_total):
                if record.tie_break:
                    entry["why_not"] = ("تعادل تام في الدرجة — حُسم بترتيب "
                                        "التسجيل (المختار سُجل أولاً)")
                else:
                    # لا تُختلق قاعدة حسم غائبة — النقص معلن في الجواب
                    # وفي تعليل البديل معاً (اتساقاً لا تناقضاً)
                    entry["why_not"] = ("تعادل تام في الدرجة — قاعدة كسر "
                                        "التعادل غير مسجلة (نقص مسمّى)")
            elif total is not None:
                entry["why_not"] = f"درجة أقل ({total:.4f})"
            else:
                entry["why_not"] = "درجته غير قابلة للمقارنة في الدليل"
            stages = cand.values_used.get("query_stages")
            if stages:
                entry["query_stages"] = stages
        alternatives.append(entry)
    return alternatives


# ---------------------------------------------------------------------------
# عدم التطابق والتعذر — لماذا لا اختيار؟
# ---------------------------------------------------------------------------

def _explain_no_match(record: Any, out: Dict[str, Any]) -> None:
    mechanism = _mechanism(record)
    out["decision_type"] = "no-match"
    if not record.candidates:
        out["answer"] = ("لا اختيار: لا مرشحين مسجلين أصلاً — "
                         "النقص معلن باسمه لا مسكوت عنه")
        out["gaps"].append("no-candidates-registered")
        return
    required = list((getattr(record, "requested", {}) or {}).get(
        "required_skills", []) or [])
    # بلا مهارات مطلوبة لا قاعدة أول-موفّر تختار أصلاً — من الدليل
    if (mechanism == "early-exit-first-supporting" and not required):
        out["answer"] = ("لا اختيار: بلا مهارات مطلوبة لا قاعدة الاختيار "
                         "تختار أصلاً (قاعدة أول-موفّر تحتاج مهارة تُسأل)")
        out["why"] = {"required_skills": []}
        return
    reasons: List[str] = []
    for cand in record.candidates:
        if cand.build_failed:
            reasons.append(f"{cand.name}: تعذر ({cand.values_used.get('failed_stage', 'evaluation')})")
        elif cand.excluded:
            reasons.append(f"{cand.name}: {cand.exclusion_reason}")
        elif mechanism == "early-exit-first-supporting":
            # قاعدة الخروج المبكر لا مفاضلة درجات أصلاً — الحالة من
            # دليل الاستعلام: استُعلم وأجاب سلباً / لم يُستعلم
            state = cand.values_used.get("query_state")
            if state == "queried":
                answers = cand.values_used.get("query_answers", {})
                reasons.append(f"{cand.name}: استُعلم وأجاب بعدم الدعم "
                               f"({answers})")
            else:
                reasons.append(f"{cand.name}: لم يُستعلم أصلاً (بلا دعم معلن)")
        elif _completed_evaluation(cand):
            reasons.append(f"{cand.name}: قُيّم ولم يُختر ({_total(cand)})")
        else:
            reasons.append(f"{cand.name}: لم يكتمل تقييمه")
    out["answer"] = ("لا اختيار: لا مرشح مؤهل — الأسباب مسماة لكل مرشح "
                     + "; ".join(reasons))
    out["why"] = {"per_candidate": reasons, "mechanism": mechanism}


def _explain_error(record: Any, out: Dict[str, Any]) -> None:
    out["decision_type"] = "error"
    # التصنيف بالدليل لا بغياب الوسم: من اكتمل تقييمه فعلاً (درجة مسجلة
    # أو حسم مسجل) ≠ من لم يُستعلم أصلاً عند توقف القرار بالتعذر
    evaluated: List[str] = []
    not_evaluated: List[str] = []
    for cand in record.candidates:
        if cand.build_failed or cand.excluded:
            continue
        if _completed_evaluation(cand):
            evaluated.append(cand.name)
        else:
            not_evaluated.append(cand.name)
    out["answer"] = ("لا اختيار: التعذر يمنع إثبات الفائز — الأخطاء مسماة "
                     "بالمرشح وموضع الفشل، ولا يُعلن فائز من مرشحين نجح "
                     "تقييم بعضهم جزئياً")
    out["why"] = {
        "errors": list(record.errors),
        "evaluated_but_no_winner_declared": evaluated,
        "not_evaluated_at_failure": not_evaluated,
    }


# ---------------------------------------------------------------------------
# نقص التعليل — مسمّى لا مطمئن
# ---------------------------------------------------------------------------

def _explain_gaps(record: Any, out: Dict[str, Any]) -> None:
    """فحص اكتمال الدليل التعليلي — كل نقص يُسمّى ولا يُخفى.

    النقص الجوهري يغيّر الجواب نفسه — لا يُضاف كحاشية على جزم مطمئن.
    وغياب البدائل ليس نقصاً إذا لم يبقَ مؤهلون آخرون أصلاً (مستبعدون
    أو متعذرون) — لا يُخترع نقص ليكمل الوصف.
    """
    if getattr(record, "policy_snapshot", None) is None:
        out["gaps"].append("policy-snapshot-absent")
    selected_ev = _selected_eval(record)
    if (out["status"] == "selected" and selected_ev is not None
            and (selected_ev.score is None
                 or getattr(selected_ev.score, "total", None) is None)
            and out["decision_type"] not in ("early-exit-first-supporting",
                                             "no-match", "error", "unknown")):
        out["gaps"].append("selected-score-missing")
        # الجواب نفسه يصرح بعدم كفاية الدليل — لا جزم مطمئن بحاشية
        out["answer"] = (
            f"الدليل لا يكفي لتعليل اختيار {record.selected}: الدرجة "
            "الحاسمة غير مسجلة — نقص مسمّى، لا تعليلاً مطمئناً")
    if out["status"] == "selected" and _ranking_missing(record):
        # فحص موحد مع المسار الحسابي: الغياب لا فراغ القائمة
        if "ranked-alternatives-missing" not in out["gaps"]:
            out["gaps"].append("ranked-alternatives-missing")
    if out["decision_type"] == "computational" and not _rules(record):
        out["gaps"].append("selection-rules-not-recorded")
    # القيود: مساهمة افتراضية معلنة — يذكرها التعليل صراحة لا كفحص ناجح
    constraint_notes = [m for m in out["missing_info"]
                        if m.startswith("constraints-not-evaluated")]
    if constraint_notes:
        out["why_note_constraints"] = (
            "القيود مساهمة افتراضية معلنة (declared-default-unevaluated) "
            "— لم تُفحص ولا توصف بأنها اجتازت فحصاً")


# ---------------------------------------------------------------------------
# أدوات قراءة القيم المسجلة — لا إعادة حساب ولا استعلام
# ---------------------------------------------------------------------------

def explain_saved_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """تفسير سجل محفوظ (قاموس مسلسل) — إعادة اشتقاق لا قراءة ``why`` القديم.

    المادة 12 (التكرار): سجل JSON محفوظ يعطي التفسير نفسه دون سياسة
    حية ولا استعلام خارجي — يُبنى كائن قراءة فوق القاموس المحفوظ
    (مفتاح ``why`` المحفوظ يُتجاهل ويُشتق من جديد).
    """
    import types

    def _cand(d: Dict[str, Any]) -> Any:
        score = d.get("score")
        return types.SimpleNamespace(
            name=d.get("name", ""),
            offered_skills=list(d.get("offered_skills", []) or []),
            values_used=dict(d.get("values_used", {}) or {}),
            score=(types.SimpleNamespace(
                total=score.get("total"),
                skill_match=score.get("skill_match"),
                priority=score.get("priority"))
                if score else None),
            excluded=bool(d.get("excluded", False)),
            exclusion_reason=d.get("exclusion_reason", ""),
            build_failed=bool(d.get("build_failed", False)),
            build_error=d.get("build_error", ""))

    policy_payload = dict(payload.get("policy", {}) or {})
    # عقد التسلسل صريح: وجود اللقطة محفوظ بعلم snapshot_present — لا
    # يُستنتج الغياب من فراغ القواعد (لقطة بقواعد فارغة حالة مختلفة)
    snapshot_present = policy_payload.get("snapshot_present", True)
    record = types.SimpleNamespace(
        decision_id=payload.get("decision_id", ""),
        kind=payload.get("kind", ""),
        requested=dict(payload.get("requested", {}) or {}),
        policy_id=policy_payload.get("policy_id", ""),
        policy_version=policy_payload.get("version", ""),
        policy_snapshot=policy_payload if snapshot_present else None,
        candidates=[_cand(c) for c in payload.get("candidates", [])],
        selected=payload.get("selected"),
        ranked_alternatives=list(payload.get("ranked_alternatives", []) or []),
        tie_break=payload.get("tie_break", ""),
        missing_info=list(payload.get("missing_info", []) or []),
        errors=list(payload.get("errors", []) or []),
        status=payload.get("status", "no_match"),
        timestamp=payload.get("timestamp", ""))
    return explain_decision(record)


def _total(cand: Any) -> Optional[float]:
    if cand is None or cand.score is None:
        return None
    total = getattr(cand.score, "total", None)
    if total is None:
        # درجة بلا إجمالي (دليل محفوظ ناقص) — ليست قيمة للمقارنة
        return None
    return float(total)


def _rule_values(cand: Any) -> Dict[str, Any]:
    """قيم القواعد المسجلة للمختار — كما استخدمت، بلا إعادة استعلام."""
    values: Dict[str, Any] = {}
    if cand.score is not None:
        values["total"] = cand.score.total
        values["skill_match"] = cand.score.skill_match
        if cand.score.priority is not None:
            values["priority"] = cand.score.priority
    if cand.values_used:
        values["recorded"] = dict(cand.values_used)
    return values


def _valid_components(selected_ev: Any, runner_ev: Any,
                      rules: Dict[str, Any]) -> Dict[str, Any]:
    """مكونات الفارق — تُعرض فقط حيث المقارنة الحسابية صالحة.

    الأولوية الثابتة (سياسة الدُبعة) أو غير المستهلكة ليست فارقاً
    أصلاً؛ والقيود مساهمة افتراضية للجميع فلا تفرّق أحداً. الأولوية
    الحقيقية تُقارن من الدرجة المسجلة عندما لا تعلن السياسة ثباتها.
    """
    components: Dict[str, Any] = {}
    sel = selected_ev.values_used
    run = runner_ev.values_used
    if "skill_match" in sel and "skill_match" in run:
        components["skill_match"] = {
            "selected": sel["skill_match"], "runner": run["skill_match"]}
    sel_basis = sel.get("priority_basis")
    run_basis = run.get("priority_basis")
    priority_contribution = rules.get("priority_contribution")
    if (sel_basis == "candidate-priority" and run_basis == "candidate-priority"
            and "priority" in sel and "priority" in run):
        components["priority"] = {
            "selected": sel["priority"], "runner": run["priority"],
            "note": "أولوية حقيقية مقروءة للطرفين — فارق صالح"}
    elif (priority_contribution not in ("constant-1.0", "unused")
          and selected_ev.score is not None and runner_ev.score is not None
          and selected_ev.score.priority is not None
          and runner_ev.score.priority is not None):
        # أولوية حقيقية في الدرجة المسجلة (مسار القدرة) — فارق صالح
        components["priority"] = {
            "selected": selected_ev.score.priority,
            "runner": runner_ev.score.priority,
            "note": "أولوية حقيقية مسجلة في الدرجة — فارق صالح"}
    if (sel_basis == "constant-1.0-not-read"
            or run_basis == "constant-1.0-not-read"
            or priority_contribution == "constant-1.0"):
        components["priority"] = {
            "note": "أولوية ثابتة معلنة في السياسة — ليست فارقاً بين المرشحين"}
    return components
