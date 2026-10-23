"""Mission types."""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class MissionStatus(Enum):
    """Mission status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ADR-0007 (R-W1-002): الحالات الدقيقة المعروفة تُترجم ملخصاً، أو تُحمل دون اختلاق مقابل.
_FINE_STATE_SUMMARY = {
    "pending": MissionStatus.PENDING,
    "created": MissionStatus.PENDING,
    "validated": MissionStatus.PENDING,
    "planned": MissionStatus.PENDING,
    "running": MissionStatus.RUNNING,
    "executing": MissionStatus.RUNNING,
    "paused": MissionStatus.RUNNING,
    "waiting_for_input": MissionStatus.RUNNING,
    "completed": MissionStatus.COMPLETED,
    "failed": MissionStatus.FAILED,
}
# حالتا حمل فقط: لا يُختلق لهما مقابل من الأربع (الإلغاء ليس فشلاً ولا اكتمالاً؛
# و«executed» حالة منتج لا دليل نجاح تنفيذي — ADR-0007 §1).
_CARRIED_ONLY_STATES = ("cancelled", "executed")


@dataclass(frozen=True)
class MissionLifecycle:
    """حامل الحالة المرتبطة بالمهمة (ADR-0007 §1).

    - ``domain``: المجال المالك للحالة (fabric/product/planning/longrunning/slice...).
    - ``fine_state``: الحالة الدقيقة كما عند مالكها؛ ``None`` = غياب صريح لحالة تنفيذ.
    - ``summary_known``: هل ملخص التنفيذ (``Mission.status``) معلوم فعلاً أم غير متاح
      (القيمة الافتراضية PENDING لا تُقدم ادعاءً حين يكون غير معلوم).
    """
    domain: str
    fine_state: Optional[str] = None
    summary_known: bool = True


def carry_lifecycle(
    domain: str,
    fine_state: Optional[str],
    *,
    execution_states: bool = True,
    previous_summary: Optional[MissionStatus] = None,
):
    """عقد ADR-0007 §1 — حوّل حالة دقيقة إلى (ملخص، حامل).

    ``execution_states=True`` لمجالات تملك تنفيذاً فعلياً (fabric/longrunning/الشريحة):
    الحالة المعروفة تُترجم ملخصاً معلوماً. ``False`` لمجالات أعلى (منتج/تخطيط):
    حالتها تُحمل ولا تدعي ملخصاً تنفيذياً. القيمة غير المعروفة ترفض صراحة،
    والغياب الصريح (``None``) جزء من العقد. الحمل دون استنتاج (الإلغاء/حالة
    المنتج/الغياب) يحفظ ملخصاً سابقاً **ومعلوميّته معاً** ولا يمحوهما.
    """
    if fine_state is not None and fine_state not in _FINE_STATE_SUMMARY \
            and fine_state not in _CARRIED_ONLY_STATES:
        raise ValueError(f"unknown fine state {fine_state!r} — ADR-0007 §1")
    if (
        fine_state is None
        or not execution_states
        or fine_state in _CARRIED_ONLY_STATES
    ):
        # حمل دون استنتاج: يبقى الملخص السابق إن كان معلوماً — بقيمته ومعلوميّته —
        # وإلا فغير معلوم (لا يُقدّم PENDING الافتراضي ادعاءً).
        known = previous_summary is not None
        return (
            previous_summary if known else MissionStatus.PENDING,
            MissionLifecycle(domain=domain, fine_state=fine_state,
                             summary_known=known),
        )
    return (_FINE_STATE_SUMMARY[fine_state],
            MissionLifecycle(domain=domain, fine_state=fine_state,
                             summary_known=True))


# ADR-0007 (R-W1-002): حقول المرجع التي تُخطر السجلات المرتبطة عند كتابتها —
# السجل إسقاط متسق للمرجع (الكتابة المحلية المباشرة تمنع الدوران).
_SYNC_FIELDS = ("id", "created_at", "started_at", "completed_at", "status", "lifecycle")

# ADR-0007 (R-W1-002): المجالات التي تملك تنفيذاً فعلياً — حدّ كتابة الحامل يشتق
# الملخص منها اتجاهاً واحداً (الحالة الدقيقة → الملخص). ما عداها (المنتج/
# التخطيط) حالتها محمولة لا تدعي ملخصاً تنفيذياً؛ والمجال غير المعروف يُعتمد
# حامله المشتق دون اختلاق ملخص (التنفيذ=حمل فقط).
_DOMAIN_EXECUTION_STATES = {
    "fabric": True,
    "longrunning": True,
    "slice": True,
    "product": False,
    "planning": False,
}


@dataclass
class Mission:
    """A mission to be executed."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    capability: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: MissionStatus = MissionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    # ADR-0007 (R-W1-002): حامل الحالة المرتبطة — ملحق بعد الحقول القائمة فلا
    # تنكسر المنشئات الموضعية، ولا يظهر في to_dict (قرار توافق منفصل).
    lifecycle: Optional[MissionLifecycle] = None

    def __setattr__(self, key, value):
        if key == "lifecycle":
            self._adopt_lifecycle(value)
            return
        # ADR-0007 §2: من يكتب الملخص (المالك التنفيذي) يثبت معلوميّته على الحامل
        # القائم — والحامل المكتوب بعده (حمل الأسر) يعيد ضبطها. لا مسار حي يتأثر
        # (المهمات النووية بلا حامل أصلاً). استبدال مباشر بلا اشتقاق متبادل:
        # الملخص هو ما يُكتب هنا، والحامل يُستبدل عبر حده لا عبر كاتب الملخص.
        rule_fired = False
        if key == "status" and "lifecycle" in self.__dict__ and self.lifecycle is not None:
            super().__setattr__(
                "lifecycle", replace(self.lifecycle, summary_known=True))
            rule_fired = True
        super().__setattr__(key, value)
        if key in _SYNC_FIELDS:
            # يُخطران معاً بعد تخزين الحقلين — لا يشاهد الإشعار نصف انتقال
            if rule_fired:
                self._notify_sync("lifecycle", self.lifecycle)
            self._notify_sync(key, value)

    def _notify_sync(self, key, value):
        """إشعار مزامنة اختياري — السجلات المرتبطة (مثل سجل الطويلة) تسقط
        حقولها المشتركة من المرجع فيتطابق المخزن الفعلي مع المرجع، بما فيها
        التغييرات المباشرة عليه. لا مراقبين على المهمات النووية الحية."""
        if "_sync_observers" in self.__dict__:
            for observer in self._sync_observers:
                observer(key, value)

    def _adopt_lifecycle(self, carrier):
        """حدّ استبدال الحامل (ADR-0007): اعتراض وتحقق قبل أي تغيير، ثم اعتماد
        الحامل وتحديث الملخص اتجاهاً واحداً (الحالة الدقيقة → الملخص وفق مجالها
        وقواعد الحمل القائمة) — عملية واحدة متسقة تمنع الدوران: لا استدعاء
        متبادل بين كاتبي status وlifecycle (الكتابات هنا تمر فوق ``__setattr__``
        مباشرة فلا قواعد تُستأنف)."""
        if carrier is None or carrier.fine_state is None:
            # الغياب (إزالة الحامل أو حالة غائبة) مرفوض لمهمة مرتبطة بسجل —
            # قبل أي تغيير، فلا تُترك حالة السجل قديمة صامتة؛ ويبقى مشروعاً
            # لطلب التخطيط.
            if self.__dict__.get("_sync_observers"):
                raise ValueError(
                    "غياب الحالة الدقيقة (أو إزالة الحامل) مرفوض لمهمة مرتبطة "
                    "بسجل (ADR-0007)؛ الغياب مشروع لطلب التخطيط فقط")
            if carrier is None:
                # إزالة الحامل — عقد المهمات النووية الأصلية (بلا حامل)
                super().__setattr__("lifecycle", None)
                self._notify_sync("lifecycle", None)
                return
            # حامل موجود بحالة غائبة: يمر بقواعد الحمل والمسار العادي أدناه —
            # لا يُعتمد كما كُتب فلا تمحو لقطة قديمة معلوميةً مثبتة، ولا يصير
            # الغياب معلوماً تلقائياً بلا تنفيذ سابق.
        # التحقق قبل أي تغيير: الحالة غير المعروفة يرفضها عقد الحمل (ValueError
        # قبل أي كتابة)، والمراقبون قد يعترضون (تمثيل تعداد الطويلة مثلاً) —
        # الرفض دون تغيير لا رفعٌ من الإشعار بعد الحفظ.
        previous = (self.status
                    if self.lifecycle is not None and self.lifecycle.summary_known
                    else None)
        summary, derived = carry_lifecycle(
            carrier.domain, carrier.fine_state,
            execution_states=_DOMAIN_EXECUTION_STATES.get(carrier.domain, False),
            previous_summary=previous)
        for validator in self.__dict__.get("_sync_validators", ()):
            validator(carrier)
        # اعتماد الحامل المشتق لكل المجالات بعد نجاح التحقق القبلي: المعلومية
        # تأتي من قواعد الحمل وحدّ الكتابة التنفيذي — لا من قيمة قديمة داخل
        # الحامل المدخل (استبدال لقطة قديمة لا يمحو معلومية تنفيذ مثبتة).
        # execution_states=False يبقى مسؤولاً عن منع استنتاج النجاح من حالة
        # منتج، مع حفظ الملخص السابق ومعلوميته أو إبقائهما غير معلومين.
        # يُخزَّن الحقلان معاً قبل أي إشعار — لا يشاهد الإشعار نصف انتقال
        super().__setattr__("lifecycle", derived)
        super().__setattr__("status", summary)
        self._notify_sync("lifecycle", derived)
        self._notify_sync("status", summary)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "capability": self.capability,
            "parameters": self.parameters,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }
