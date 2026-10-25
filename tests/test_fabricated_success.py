"""النجاح الوهمي مرفوض (ADR-0008) — إصلاح العيوب المسماة في سجل العمل 0089.

العقد: لا يُدَّعى اكتمالُ عملٍ لم يُنفَّذ — من لا ينفذ عملاً حقيقياً
يعلن `not_executed` صراحة بسبب (كسابقة workflow الحضاري المعتمدة)، ولا
يغير حالته إلى «مكتمل»، ولا يرفع الادعاء سلسلةً إلى مستدعيه.

العيوب المسماة (أحمر أولاً ثم إصلاح أدنى — قرار المالك 2026-10-25):
- `AutonomousOrchestrator.execute` يعيد `{'executed': True, ...}` بلا أي عمل.
- `MergeExecutor.execute` يعيد `{'merged': True, ...}` بلا أي عمل.
- والمستدعيان الخارجيان يرفعان الادعاء: `AutonomousRuntime.execute_mission`
  (نجاح + حالة مكتمل دائماً) و`IntegrationEngine.integrate`
  (integrated=True من فبركة المدققين).
"""
from agos_kernel.civilization.autonomous_engineering.autonomous_batch import (
    AutonomousOrchestrator,
    AutonomousRuntime,
)
from agos_kernel.civilization.autonomous_engineering.platform_batch import (
    IntegrationEngine,
    MergeExecutor,
)

PLAN = {"phases": ["analysis"], "plan_id": "p1"}


# ---------- العيب الأول: AutonomousOrchestrator.execute ----------

def test_orchestrator_does_not_claim_execution_without_work():
    """لا ادعاء تنفيذ بلا عمل: المخرج لا يحمل executed=True، ويعلن
    not_executed صراحة بسبب — لا نجاحاً وهمياً ولا صمتاً."""
    result = AutonomousOrchestrator().execute(PLAN)
    assert result.get("executed") is not True
    assert result.get("status") == "not_executed"
    assert result.get("reason")  # سبب صريح لا صمت


def test_autonomous_runtime_does_not_claim_success_without_execution():
    """المستدعي الخارجي لا يرفع الادعاء: المهمة لا تُعاد ناجحة والحالة لا
    تصير «مكتملة» وقد لم يُنفَّذ شيء."""
    runtime = AutonomousRuntime()
    outcome = runtime.execute_mission({"id": "m1"})
    assert outcome.get("status") != "success"
    assert outcome.get("status") == "not_executed"
    assert runtime.state.value != "completed"


# ---------- العيب الثاني: MergeExecutor.execute ----------

def test_merge_executor_does_not_claim_merge_without_work():
    """لا ادعاء دمج بلا عمل: المخرج لا يحمل merged=True، ويعلن not_executed
    صراحة بسبب."""
    result = MergeExecutor().execute({"merge_plan": [], "order": []})
    assert result.get("merged") is not True
    assert result.get("status") == "not_executed"
    assert result.get("reason")  # سبب صريح لا صمت


def test_integration_engine_does_not_claim_integrated_without_merge():
    """المستدعي الخارجي لا يرفع الادعاء: التكامل لا يُعاد integrated=True
    وقد لم يُنفَّذ دمج فعلي."""
    outcome = IntegrationEngine().integrate([{"patch": 1}])
    assert outcome.get("integrated") is not True
    assert outcome.get("status") == "not_executed"
