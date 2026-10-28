"""AGOS Execution Engine - Production Implementation."""
import asyncio
import copy
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ExecutionEvent(Enum):
    """Execution events."""
    STARTED = "started"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"
    CHECKPOINT = "checkpoint"
    RETRY = "retry"


@dataclass
class ExecutionContext:
    """Execution context."""
    execution_id: str
    mission_id: str
    capability_id: str
    skill_id: str
    provider_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[Dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class ExecutionResult:
    """Execution result."""
    execution_id: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    trace: List[Dict] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)


@dataclass
class InvocationOutcome:
    """نتيجة استدعاء متزامن واحد (ADR-0008 — R-W1-003): النجاح يُعرف بخلوّ
    الخطأ — القيم ``None``/``False``/``0`` نجاحات مشروعة، لا صدقُ القيمة."""
    value: Any = None
    error: Optional[Exception] = None

    @property
    def ok(self) -> bool:
        """النجاح = غياب الخطأ (لا صدق القيمة)."""
        return self.error is None


class ExecutionPolicy:
    """Execution policy."""
    
    def __init__(self):
        self.timeout_seconds: int = 300
        self.max_retries: int = 3
        self.retry_delay_seconds: float = 1.0
        self.rollback_on_failure: bool = True
        self.checkpoint_interval_seconds: int = 60
        self.enable_telemetry: bool = True
        self.enable_tracing: bool = True


class ExecutionNode:
    """A single execution node in a workflow."""
    
    def __init__(
        self,
        node_id: str,
        name: str,
        skill: str,
        provider: str,
        input_map: Dict[str, str] = None,
        condition: str = None,
        retry_policy: Dict = None,
    ):
        self.node_id = node_id
        self.name = name
        self.skill = skill
        self.provider = provider
        self.input_map = input_map or {}
        self.condition = condition
        self.retry_policy = retry_policy or {"max_retries": 3, "delay": 1.0}
        self.status: ExecutionStatus = ExecutionStatus.PENDING
        self.result: Any = None
        self.error: Optional[str] = None
        self.attempts: int = 0


class ExecutionGraph:
    """Compiled workflow execution graph."""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.nodes: Dict[str, ExecutionNode] = {}
        self.edges: Dict[str, List[str]] = {}  # node_id -> [dependent_node_ids]
        self.entry_nodes: List[str] = []
        self.exit_nodes: List[str] = []
    
    def add_node(self, node: ExecutionNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
        if node.node_id not in self.edges:
            self.edges[node.node_id] = []
    
    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add an edge between nodes."""
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)
    
    def get_ready_nodes(self, completed: set) -> List[ExecutionNode]:
        """Get nodes that are ready to execute."""
        ready = []
        for node_id, deps in self.edges.items():
            if node_id in completed:
                continue
            if all(dep in completed for dep in deps):
                node = self.nodes.get(node_id)
                if node:
                    ready.append(node)
        return ready


class ExecutionEngine:
    """Production execution engine."""
    
    def __init__(self):
        self.policies: Dict[str, ExecutionPolicy] = {}
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.completed_executions: Dict[str, ExecutionResult] = {}
        self.event_handlers: Dict[ExecutionEvent, List[Callable]] = {}
        self._metrics: Dict[str, List[float]] = {}
        self._traces: Dict[str, List[Dict]] = {}
        # مهمة التنفيذ الداخلية وطلب الإلغاء الصريح (سجل العمل 0082):
        # الفهرسان يحددان نافذة العمل القابل للإلغاء — من تسجيل المهمة
        # حتى انتهاء المسار فعلياً في finally
        self._execution_tasks: Dict[str, Any] = {}
        self._cancel_requests: Dict[str, bool] = {}
        # معاملات إعادة التنفيذ (المادة 14 — Replayable، سجل العمل 0106):
        # تُخزَّن مع النتيجة في النافذة نفسها — لقطة عميقة (نمط سجل
        # العمل 0081) تحمي الإعادة من تعديل المعاملات لاحقاً؛ الإعادة
        # الفعلية عبر execute نفسها لا نتيجة مخزنة
        self._replay_parameters: Dict[str, tuple] = {}
    
    def invoke_sync(self, func, *args, **kwargs) -> InvocationOutcome:
        """الواجهة المتزامنة للنواة المشتركة (ADR-0008): استدعاء واحد بلا مهلة
        ولا إعادة — سياسة المسار الحي محفوظة. تلتقط أخطاء العمل العادية
        (``Exception`` فقط — استثناءات التحكم كـKeyboardInterrupt تمر كما هي)،
        والعمل غير المتزامن مرفوض صراحةً دون تشغيله (لا جسر asyncio.run هنا —
        استخدم ``execute`` غير المتزامن له)."""
        if inspect.iscoroutinefunction(func):
            return InvocationOutcome(
                error=TypeError(
                    "invoke_sync يرفض الدوال غير المتزامنة (ADR-0008) — "
                    "استخدم ExecutionEngine.execute"))
        try:
            result = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — أخطاء العمل العادية فقط
            return InvocationOutcome(error=e)
        if inspect.isawaitable(result):
            # كوروتين غير منفّذ ليس نجاحاً — لا إغلاق اعتباطي لكل awaitable
            # (لا دلالة إغلاق موحدة): الكوروتين الفعلي وحده يُغلق لمنع تحذير
            # عدم الانتظار، وأي خطأ إغلاق عادي يبقى داخل عقد المخرج، وبقية
            # awaitables تُرفض بوضوح دون تشغيلها (BaseException يمر كما هو).
            if inspect.iscoroutine(result):
                try:
                    result.close()
                except Exception as close_error:  # noqa: BLE001 — عقد المخرج
                    return InvocationOutcome(error=close_error)
            return InvocationOutcome(
                error=TypeError(
                    "invoke_sync لا يعيد كوروتيناً غير منفّذ (ADR-0008) — "
                    "استخدم ExecutionEngine.execute"))
        return InvocationOutcome(value=result)

    def create_policy(self, name: str, **kwargs) -> ExecutionPolicy:
        """Create an execution policy."""
        policy = ExecutionPolicy()
        for key, value in kwargs.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        self.policies[name] = policy
        return policy
    
    def get_policy(self, name: str) -> ExecutionPolicy:
        """Get an execution policy."""
        return self.policies.get(name, ExecutionPolicy())
    
    def on_event(self, event: ExecutionEvent, handler: Callable) -> None:
        """Register an event handler."""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def _emit_event(self, event: ExecutionEvent, context: ExecutionContext, data: Dict = None) -> None:
        """Emit an execution event."""
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(context, data or {})
            except Exception as exc:
                # العزل مقصود وسليم (المستمع الفاشل لا يكسر التنفيذ) —
                # الصمت هو المخالفة (المادة 6: تشخيص لكل فشل): أثر مسمى
                # في قناة التشخيص القياسية يحمل التنفيذ والحدث وهوية
                # المستمع (اسماً مستقراً) ونوع الاستثناء وسببه بتتبعه. لا
                # يُصدر عبر _emit_event نفسه (لا عودية) ولا يغير دلالات
                # الإلغاء.
                logger.error(
                    "event-listener-failed execution_id=%s event=%s "
                    "listener=%s error=%s: %s",
                    context.execution_id, event.name,
                    getattr(handler, "__qualname__", None)
                    or type(handler).__qualname__,
                    type(exc).__name__, exc,
                    exc_info=True)
    
    async def execute(
        self,
        capability_id: str,
        skill_id: str,
        provider_id: str,
        parameters: Dict[str, Any],
        policy_name: str = "default",
    ) -> ExecutionResult:
        """Execute a capability skill with provider."""
        execution_id = str(uuid.uuid4())
        context = ExecutionContext(
            execution_id=execution_id,
            mission_id="",
            capability_id=capability_id,
            skill_id=skill_id,
            provider_id=provider_id,
            parameters=parameters,
        )
        
        policy = self.get_policy(policy_name)
        self.active_executions[execution_id] = context

        # لقطة معاملات الإعادة (المادة 14 — سجل العمل 0106): تُلتقط قبل
        # العمل — المدخل كما ورد لا الحالة النهائية بعد تعديل العمل؛
        # وفشلها العادي لا يغيّر نتيجة التنفيذ ولا يمنع تنظيفه — الإعادة
        # عندئذ خطأ صريح عند الطلب. موضعها داخل نطاق الحماية عمداً:
        # استثناء التحكم (CancelledError) من النسخ ينتشر كما هو ولا
        # يستدعي العمل، لكنه لا يتجاوز التنظيف — الفهرس لا يُسرَّب أبداً
        _replay_params: Optional[Any] = None

        start_time = datetime.now()
        execution_result = None
        inner_task = None

        try:
            try:
                _replay_params = copy.deepcopy(parameters)
            except Exception:  # noqa: BLE001 — فشل اللقطة شأن إعادة لا شأن التنفيذ
                _replay_params = None

            # مهمة داخلية يملكها المحرك (سجل العمل 0082): تُسجَّل قبل إصدار
            # STARTED — فمستمع البدء يستطيع طلب الإلغاء فوراً قبل أي أثر
            # للمهارة؛ ولا يُستخدم current_task لإلغاء مهمة المستدعي قط
            # (إلغاء المستدعي شأن مستقل ينتشر كما هو) — يُستخدم فقط لفحص
            # حالة الإلغاء المعلقة لمهمة المستدعي عند تمييز المصدر
            inner_task = asyncio.ensure_future(
                self._execute_skill(context, policy))
            self._execution_tasks[execution_id] = inner_task
            self._emit_event(ExecutionEvent.STARTED, context)

            # Simulate execution with timeout
            result = await asyncio.wait_for(
                inner_task,
                timeout=policy.timeout_seconds
            )

            status = ExecutionStatus.COMPLETED
            context.completed_at = datetime.now()
            self._emit_event(ExecutionEvent.COMPLETED, context)

            execution_result = ExecutionResult(
                execution_id=execution_id,
                status=status,
                output=result,
                metrics=self._compute_metrics(execution_id, start_time),
            )

        except asyncio.CancelledError:
            # تمييز مصدر الإلغاء تزامنياً (تصحيح المراجعة — سجل العمل
            # 0082): العلامة وحدها لا تكفي — إن طلب المحرك الإلغاء ثم
            # ألغى المستدعي مهمته قبل معالجة الطلب، بقيت العلامة True
            # فيبتلع الفرع إلغاء المستدعي ويعيد نتيجة عادية. الفيصل:
            # هل لمهمة المستدعي نفسها طلب إلغاء معلق (cancelling) —
            # فحص حالة الإلغاء لا إلغاء المهمة (المنع السابق كان على
            # استخدام current_task لإلغاء مهمة المستدعي)
            current = asyncio.current_task()
            caller_cancel_pending = (
                current is not None and current.cancelling() > 0)
            if (not caller_cancel_pending
                    and self._cancel_requests.get(execution_id)):
                # إلغاء صريح من المحرك (طلب cancel): النهاية الفعلية هنا —
                # نتيجة إلغاء صريحة وحدث CANCELLED واحد مؤكد (لا عند مجرد
                # قبول الطلب)
                execution_result = ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.CANCELLED,
                    error="Execution cancelled by request",
                )
                self._emit_event(ExecutionEvent.CANCELLED, context)
            else:
                # إلغاء المستدعي لمهمته (أو سباق المصدرين) — أوقف العمل
                # الداخلي ثم انتشر الانتشار كما هو: لا يتحول بصمت إلى
                # نتيجة عادية حتى لو كانت علامة طلب المحرك مثبتة
                if inner_task is not None and not inner_task.done():
                    inner_task.cancel()
                raise

        except asyncio.TimeoutError:
            status = ExecutionStatus.FAILED
            execution_result = ExecutionResult(
                execution_id=execution_id,
                status=status,
                error=f"Execution timed out after {policy.timeout_seconds}s",
            )
            self._emit_event(ExecutionEvent.FAILED, context)

        except Exception as e:
            status = ExecutionStatus.FAILED
            execution_result = ExecutionResult(
                execution_id=execution_id,
                status=status,
                error=str(e),
            )
            self._emit_event(ExecutionEvent.FAILED, context)

        finally:
            # تخزين محروس — الاستثناء المنتشر (إلغاء المستدعي) لا يترك
            # نتيجة نصف مكتملة ولا خطأ متغير غير مهيأ
            if execution_result is not None:
                self.completed_executions[execution_id] = execution_result
                # معاملات الإعادة: اللقطة الملتقطة قبل العمل (المدخل كما
                # ورد) — لا نسخ هنا في finally كي لا يحوّل فشل النسخ نجاحاً
                # إلى استثناء ولا يمنع التنظيف؛ وغياب اللقطة يعني لا إعادة
                # (خطأ صريح عند طلبها)
                if _replay_params is not None:
                    self._replay_parameters[execution_id] = (
                        capability_id, skill_id, provider_id,
                        _replay_params, policy_name)
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
            self._execution_tasks.pop(execution_id, None)
            self._cancel_requests.pop(execution_id, None)

        return execution_result
    
    async def _execute_skill(
        self,
        context: ExecutionContext,
        policy: ExecutionPolicy,
    ) -> Any:
        """Execute skill with retry logic."""
        max_retries = policy.max_retries
        delay = policy.retry_delay_seconds
        
        for attempt in range(max_retries + 1):
            try:
                # Simulate skill execution
                result = await self._skill_logic(context)
                return result
            except Exception as e:
                if attempt < max_retries:
                    context.state["last_error"] = str(e)
                    context.state["retry_attempt"] = attempt + 1
                    self._emit_event(ExecutionEvent.RETRY, context)
                    await asyncio.sleep(delay * (attempt + 1))
                else:
                    raise
        
        raise RuntimeError("Max retries exceeded")
    
    async def _skill_logic(self, context: ExecutionContext) -> Any:
        """Actual skill execution logic."""
        # This would be replaced by real skill implementation
        skill_id = context.skill_id
        params = context.parameters
        
        # Simulate async skill execution
        await asyncio.sleep(0.1)
        
        return {
            "skill": skill_id,
            "input": params,
            "output": f"Result of {skill_id}",
            "timestamp": datetime.now().isoformat(),
        }
    
    async def execute_workflow(
        self,
        graph: ExecutionGraph,
        initial_parameters: Dict[str, Any],
        policy_name: str = "default",
    ) -> Dict[str, ExecutionResult]:
        """Execute a compiled workflow graph."""
        policy = self.get_policy(policy_name)
        results: Dict[str, ExecutionResult] = {}
        completed: set = set()
        context_state: Dict[str, Any] = initial_parameters.copy()
        
        while len(completed) < len(graph.nodes):
            ready_nodes = graph.get_ready_nodes(completed)
            if not ready_nodes:
                break
            
            # Execute ready nodes in parallel
            tasks = []
            for node in ready_nodes:
                context = ExecutionContext(
                    execution_id=str(uuid.uuid4()),
                    mission_id="",
                    capability_id="workflow",
                    skill_id=node.skill,
                    provider_id=node.provider,
                    parameters={k: context_state.get(v) for k, v in node.input_map.items()},
                    state=context_state.copy(),
                )
                task = self.execute(
                    capability_id="workflow",
                    skill_id=node.skill,
                    provider_id=node.provider,
                    parameters=context.parameters,
                    policy_name=policy_name,
                )
                tasks.append((node.node_id, task))
            
            for node_id, task in tasks:
                result = await task
                results[node_id] = result
                node = graph.nodes[node_id]
                node.status = result.status
                node.result = result.output
                
                if result.status == ExecutionStatus.COMPLETED:
                    completed.add(node_id)
                    context_state[node_id] = result.output
                elif result.status == ExecutionStatus.FAILED:
                    completed.add(node_id)  # Mark as done even if failed
        
        return results
    
    def pause(self, execution_id: str) -> bool:
        """التقاط نقطة تحقق مع حدثَي CHECKPOINT وPAUSED (المادة 14 — سجل العمل 0107).

        حد معلن: هذا لا يعلّق العمل الجاري — التعليق الفعلي تعاوني
        عند نقاط انتظار العمل ولا آلية له في هذا المسار (Recoverable
        مفتوحة)؛ الدليل الرصدي: العمل يكتمل بعد عودة True. لقطة
        النقطة نسخة عميقة مستقلة تُجهَّز قبل الإلحاق والأحداث، وفشل
        نسخها ينتشر صريحاً — لا نجاح يُعلن عن لقطة فاشلة.
        """
        context = self.active_executions.get(execution_id)
        if not context:
            return False

        checkpoint = self.checkpoint(execution_id)
        self._emit_event(ExecutionEvent.CHECKPOINT, context)
        self._emit_event(ExecutionEvent.PAUSED, context)
        return True
    
    def resume(self, execution_id: str) -> bool:
        """استعادة بيانات السياق من آخر نقطة تحقق (سجل العمل 0107).

        حد معلن: هذا يستعيد الحالة والمعاملات بنسخ مستقلة عن النقطة
        المخزنة — لا يستأنف موضع coroutine (لا تعليق فعلي قائم
        يُستأنف). النسخة المستعادة مستقلة فتبقى النقطة قابلة
        للاستعادة مراراً، وفشل النسخ يترك السياق دون تغيير (لا
        استعادة نصفية).
        """
        context = self.active_executions.get(execution_id)
        if not context or not context.checkpoints:
            return False
        
        # Restore from last checkpoint — النسختان تُجهَّزان في متغير
        # محلي قبل تعديل أي حقل في السياق، من بنية واحدة تحفظ
        # العلاقات المشتركة بين الحالة والمعاملات
        checkpoint = context.checkpoints[-1]
        restored = copy.deepcopy(
            {"state": checkpoint["state"], "parameters": checkpoint["parameters"]})
        context.state = restored["state"]
        context.parameters = restored["parameters"]
        self._emit_event(ExecutionEvent.RESUMED, context)
        return True
    
    def cancel(self, execution_id: str) -> bool:
        """طلب إلغاء تنفيذ جارٍ — قبول الطلب لا اكتماله.

        يعيد True إذا قُبل الطلب (معرّف عمل داخلي جارٍ لم يُطلب إلغاؤه
        سابقاً)، ويعيد False للمجهول أو المنتهي أو الطلب المكرر. النتيجة
        النهائية وحدث CANCELLED تصفان النهاية الفعلية داخل execute — لا
        يُعلن الاكتمال هنا، ولا يُنظف الفهرس قبل انتهاء المسار فعلياً
        (إصلاح الإلغاء الحقيقي — سجل العمل 0082: الإلغاء السابق كان إدارة
        فهرس فقط والعمل يستمر حتى الاكتمال بنجاح بعد الإلغاء)."""
        if self._cancel_requests.get(execution_id):
            return False                       # طلب مكرر
        task = self._execution_tasks.get(execution_id)
        if task is None:
            return False                        # مجهول أو انتهى مساره
        if task.done():
            return False                        # العمل انتهى فعلاً — لا طلب
        if not task.cancel():
            return False                        # المهمة لا تقبل الإلغاء
        self._cancel_requests[execution_id] = True
        return True
    
    def checkpoint(self, execution_id: str) -> Optional[Dict]:
        """Create a checkpoint for an execution.

        حد معلن (سجل العمل 0107): اللقطة نسخة عميقة مستقلة للحالة
        والمعاملات تُجهَّز قبل الإلحاق — تعديل السياق الحي بعدها لا
        يلوثها، وكل استعادة تنال نسخة منها. فشل النسخ ينتشر صريحاً:
        لا نقطة تُنشأ ولا نجاح يُعلن عن لقطة فاشلة.
        """
        context = self.active_executions.get(execution_id)
        if not context:
            return None
        
        # نسخة واحدة للبنية الكاملة تحفظ العلاقات المشتركة بين
        # الحالة والمعاملات، وتُجهَّز قبل أي نشر (إلحاق أو أحداث)
        snapshot = copy.deepcopy(
            {"state": context.state, "parameters": context.parameters})
        checkpoint = {
            "execution_id": execution_id,
            "state": snapshot["state"],
            "parameters": snapshot["parameters"],
            "timestamp": datetime.now().isoformat(),
        }
        context.checkpoints.append(checkpoint)
        return checkpoint
    
    async def replay(self, execution_id: str) -> ExecutionResult:
        """إعادة تنفيذ اكتمل فعلاً بنفس معاملاته (المادة 14 — Replayable).

        عقد الطريقة القائم في وثيقتها: «إعادة تشغيل بنفس المعاملات»
        («Re-run with same parameters») — والتنفيذ الفعلي عبر ``execute``
        نفسها بتنفيذ جديد ومعرّف جديد ونتيجة جديدة. المعاملات من لقطة
        ملتقطة قبل العمل الأصلي (المدخل كما ورد — نمط سجل العمل 0081)،
        وكل إعادة تنال نسخة مستقلة منها فلا تلوث متبادلاً عبر السجل؛
        والنتيجة الأصلية المخزنة تبقى مستقلة، والمجهول يبقى
        ``ValueError`` كما كان. المعاملات غير القابلة للقطة (فشل نسخها
        لا يغيّر نتيجة التنفيذ الأصلي ولا تنظيفه) إعادتها خطأ صريح
        هنا. (قبل سجل العمل 0106 كان هذا الادعاء وهمياً: إعادة النتيجة
        المخزنة بلا تنفيذ — والتعليق القديم في الكود كان يقر بذلك.)
        """
        if execution_id not in self.completed_executions:
            raise ValueError(f"Execution {execution_id} not found")
        args = self._replay_parameters.get(execution_id)
        if args is None:
            raise ValueError(
                f"Execution {execution_id} has no replay parameters")
        capability_id, skill_id, provider_id, replay_params, policy_name = args
        # نسخة مستقلة لكل إعادة: عمل معاد يعدّل معامله لا يلوث سجل
        # الإعادة ولا الإعادات اللاحقة
        return await self.execute(
            capability_id, skill_id, provider_id,
            copy.deepcopy(replay_params), policy_name)
    
    def rollback(self, execution_id: str) -> bool:
        """إصدار حدث ROLLED_BACK للمسار الجاري فقط (سجل العمل 0107).

        حد معلن: هذا لا يعكس أي آثار — العكس الفعلي للآثار آلية
        غير متوفرة في هذا المسار (Recoverable مفتوحة) ومسؤولية
        مجالية إن وُجدت لاحقاً؛ الدليل الرصدي: التنفيذ يكتمل بعد
        عودة True.
        """
        context = self.active_executions.get(execution_id)
        if not context:
            return False
        
        self._emit_event(ExecutionEvent.ROLLED_BACK, context)
        return True
    
    def _compute_metrics(self, execution_id: str, start_time: datetime) -> Dict[str, float]:
        """Compute execution metrics."""
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "duration_seconds": duration,
            "memory_mb": 0,  # Would be measured in production
            "cpu_percent": 0,  # Would be measured in production
        }
    
    def get_metrics(self, execution_id: str) -> Optional[Dict[str, List[float]]]:
        """Get metrics for an execution."""
        return {"execution_time": self._metrics.get(execution_id, [])}
    
    def get_trace(self, execution_id: str) -> Optional[List[Dict]]:
        """Get trace for an execution."""
        return self._traces.get(execution_id, [])
    
    def get_active_count(self) -> int:
        """Get count of active executions."""
        return len(self.active_executions)
    
    def get_completed_count(self) -> int:
        """Get count of completed executions."""
        return len(self.completed_executions)


# Global engine instance
_engine = ExecutionEngine()


def get_engine() -> ExecutionEngine:
    """Get the global execution engine."""
    return _engine