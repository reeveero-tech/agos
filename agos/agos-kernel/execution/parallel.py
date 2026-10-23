"""Universal Parallel Execution Engine."""
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class ExecutionMode(Enum):
    """Execution mode."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
    DISTRIBUTED = "distributed"


class ExecutionStatus(Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionTask:
    """A single execution task."""
    id: str
    name: str
    func: Callable = field(default_factory=lambda: None)
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ExecutionBatch:
    """A batch of tasks that can run in parallel."""
    id: str
    tasks: List[ExecutionTask] = field(default_factory=list)
    max_parallelism: int = 10
    created_at: datetime = field(default_factory=datetime.now)


class ParallelScheduler:
    """Parallel task scheduler."""
    
    def __init__(self, max_workers: int = 10):
        """Initialize scheduler."""
        self.max_workers = max_workers
        self.tasks: Dict[str, ExecutionTask] = {}
    
    def _generate_id(self, name: str) -> str:
        """Generate unique ID."""
        unique = f"{name}-{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique.encode()).hexdigest()[:16]
    
    def add_task(
        self,
        name: str,
        dependencies: Optional[List[str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> ExecutionTask:
        """Add a task to the scheduler.

        ``task_id`` (R-Q-001): معرف اختياري للمهمة القائمة أصلاً — بدونه تُولّد مهمة
        بمعرف جديد بينما تبعياتها تشير لمعرفات المهمة الأصلية فلا تكتمل السلسلة أبداً.
        """
        task = ExecutionTask(
            id=task_id or self._generate_id(name),
            name=name,
            dependencies=dependencies or [],
            resources=resources or {},
        )
        self.tasks[task.id] = task
        return task
    
    def get_ready_tasks(self) -> List[ExecutionTask]:
        """Get tasks that are ready to execute."""
        ready = []
        completed = {
            tid for tid, t in self.tasks.items()
            if t.status == ExecutionStatus.COMPLETED
        }
        
        for task in self.tasks.values():
            if task.status != ExecutionStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            if all(dep in completed for dep in task.dependencies):
                ready.append(task)
        
        return ready[:self.max_workers]
    
    def get_parallel_batches(self) -> List[List[ExecutionTask]]:
        """Get tasks grouped into parallel batches."""
        batches = []
        pending = set(self.tasks.keys())
        completed = set()
        
        while pending:
            batch = []
            remaining = []
            
            for task_id in pending:
                task = self.tasks[task_id]
                deps_met = all(dep in completed for dep in task.dependencies)
                
                if deps_met and len(batch) < self.max_workers:
                    batch.append(task)
                else:
                    remaining.append(task_id)
            
            if not batch:
                break
            
            batches.append(batch)
            for task in batch:
                completed.add(task.id)
            pending = set(remaining)
        
        return batches


class DependencyAnalyzer:
    """Analyze task dependencies."""
    
    def analyze(self, tasks: List[ExecutionTask]) -> Dict[str, List[str]]:
        """Analyze dependencies between tasks."""
        graph: Dict[str, List[str]] = {}
        
        for task in tasks:
            graph[task.id] = task.dependencies.copy()
        
        return graph
    
    def find_cycles(self, tasks: List[ExecutionTask]) -> List[List[str]]:
        """Find circular dependencies."""
        graph = self.analyze(tasks)
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for dep in graph.get(node, []):
                if dep not in visited:
                    dfs(dep, path)
                elif dep in rec_stack:
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:] + [dep])
            
            path.pop()
            rec_stack.remove(node)
        
        for task in tasks:
            if task.id not in visited:
                dfs(task.id, [])
        
        return cycles


class ConflictDetector:
    """Detect resource conflicts."""
    
    def __init__(self):
        """Initialize detector."""
        self.resource_locks: Dict[str, Set[str]] = {}
    
    def detect_conflicts(
        self,
        tasks: List[ExecutionTask],
    ) -> List[tuple]:
        """Detect conflicts between tasks."""
        conflicts = []
        active_tasks: Dict[str, Set[str]] = {}
        
        for task in tasks:
            for resource, value in task.resources.items():
                if resource in active_tasks:
                    # Conflict detected
                    for other_task_id in active_tasks[resource]:
                        conflicts.append((task.id, other_task_id, resource))
        
        return conflicts
    
    def acquire_lock(self, task_id: str, resource: str) -> bool:
        """Acquire a resource lock."""
        if resource not in self.resource_locks:
            self.resource_locks[resource] = set()
        
        self.resource_locks[resource].add(task_id)
        return True
    
    def release_lock(self, task_id: str, resource: str) -> bool:
        """Release a resource lock."""
        if resource in self.resource_locks:
            self.resource_locks[resource].discard(task_id)
        return True


class ResourceCoordinator:
    """Coordinate resource allocation."""
    
    def __init__(self):
        """Initialize coordinator."""
        self.resources: Dict[str, Dict[str, Any]] = {}
    
    def register_resource(self, name: str, capacity: float = 1.0) -> None:
        """Register a resource."""
        self.resources[name] = {
            "capacity": capacity,
            "allocated": 0.0,
        }
    
    def allocate(self, resource: str, amount: float) -> bool:
        """Allocate resource."""
        if resource not in self.resources:
            return False
        
        r = self.resources[resource]
        if r["allocated"] + amount > r["capacity"]:
            return False
        
        r["allocated"] += amount
        return True
    
    def release(self, resource: str, amount: float) -> bool:
        """Release resource."""
        if resource not in self.resources:
            return False
        
        self.resources[resource]["allocated"] = max(0, self.resources[resource]["allocated"] - amount)
        return True


class ParallelExecutor:
    """Universal Parallel Execution Engine."""
    
    def __init__(self, max_workers: int = 10):
        """Initialize executor."""
        self.scheduler = ParallelScheduler(max_workers)
        self.dependency_analyzer = DependencyAnalyzer()
        self.conflict_detector = ConflictDetector()
        self.resource_coordinator = ResourceCoordinator()
        self.execution_batches: List[ExecutionBatch] = []
    
    def _begin_attempt(self, task: ExecutionTask) -> None:
        """إعادة ضبط حقول المحاولة الجارية موحدة (ADR-0008 — R-W1-003): قبل أي
        تحليل أو منع أو عودة مبكرة — لا بقايا من محاولة سابقة عند إعادة
        الاستخدام (نجاح قديم، خطأ قديم، طوابع بدء/إكمال قديمة)."""
        task.result = None
        task.error = None
        task.started_at = None
        task.completed_at = None

    def _invoke_original(self, core, task: ExecutionTask,
                         results: Dict[str, ExecutionStatus],
                         failed: set) -> None:
        """استدعاء المهمة الأصلية عبر النواة المشتركة (ADR-0008 — R-W1-003):
        حقول المحاولة أعيد ضبطها موحدة عند دخول الطريقتين؛ النتيجة/الخطأ
        يُكتبان على المهمة الأصلية نفسها؛ التابعة لا تعمل بعد فشل سابقتها؛
        وغياب func فشل صريح لا نجاح."""
        blocked = [d for d in task.dependencies if d in failed]
        if blocked:
            task.status = ExecutionStatus.FAILED
            task.error = f"تبعية فاشلة: {blocked[0]}"
            results[task.id] = ExecutionStatus.FAILED
            failed.add(task.id)
            return
        if not callable(task.func):
            task.status = ExecutionStatus.FAILED
            task.error = "لا عمل قابل للتنفيذ (func غائبة)"
            results[task.id] = ExecutionStatus.FAILED
            failed.add(task.id)
            return
        task.started_at = datetime.now()
        outcome = core.invoke_sync(task.func, *task.args, **task.kwargs)
        if outcome.error is not None:
            task.status = ExecutionStatus.FAILED
            task.error = str(outcome.error)
            results[task.id] = ExecutionStatus.FAILED
            failed.add(task.id)
            return
        task.status = ExecutionStatus.COMPLETED
        task.result = outcome.value
        task.completed_at = datetime.now()
        results[task.id] = ExecutionStatus.COMPLETED

    def execute(self, tasks: List[ExecutionTask]) -> Dict[str, ExecutionStatus]:
        """تنفيذ المهام (ADR-0008 — R-W1-003): تحليل التبعيات والدورات الحقيقي
        محفوظ، والعمل يُستدعى فعلياً عبر النواة المشتركة مرتبطاً بالمهمة
        **الأصلية** بالهوية. الجاهزية **إيجابية** من نتائج هذا الاستدعاء — لا
        من سجل المجدول (المجدول سجل حالة لـget_stats فقط). التنفيذ **تسلسلي**
        موثّق بلا ادعاء توازٍ. كل مهمة تنال مخرجاً صريحاً (لا صمت)."""
        from agos_kernel.execution.engine import get_engine
        core = get_engine()
        by_id = {t.id: t for t in tasks}
        results: Dict[str, ExecutionStatus] = {}
        failed: set = set()

        # إعادة ضبط حقول المحاولة موحدة قبل أي تحليل أو منع أو عودة مبكرة
        for task in tasks:
            self._begin_attempt(task)

        # Analyze dependencies
        cycles = self.dependency_analyzer.find_cycles(tasks)
        if cycles:
            for task in tasks:
                task.status = ExecutionStatus.FAILED
                task.error = f"دورة تبعيات: {cycles[0]}"
                results[task.id] = ExecutionStatus.FAILED
                failed.add(task.id)
                self._sync_scheduled_copy(task)
            return results

        # Detect conflicts
        conflicts = self.conflict_detector.detect_conflicts(tasks)
        if conflicts:
            # Resolve by serializing conflicting tasks
            pass

        # سجل المجدول (لـget_stats) — بهوية المهمة الأصلية (R-Q-001)؛ الجاهزية
        # لا تُحتسب منه
        for task in tasks:
            self.scheduler.add_task(
                name=task.name,
                dependencies=task.dependencies,
                resources=task.resources,
                task_id=task.id,   # R-Q-001: هوية المهمة الأصلية — وإلا انكسرت التبعيات
            )

        # الجاهزية **إيجابية**: تُحتمل من نتائج الاستدعاء الحالي وحده — التبعية
        # تعتبر مقضية فقط إذا كانت في نتائج هذا الاستدعاء بحالة COMPLETED.
        # لا اعتماد على سجل المجدول القديم (إعادة استخدام المنفذ عبر استدعاءات
        # سابقة لا تُشغّل تابعة بصمت اعتماداً على اكتمال قديم). التنفيذ تسلسلي
        # موثّق بلا ادعاء توازٍ.
        pending = list(tasks)
        while True:
            progressed = False
            for task in list(pending):
                absent = [d for d in task.dependencies if d not in by_id]
                if absent:
                    task.error = f"تبعية غير متاحة: {absent[0]}"
                    task.status = ExecutionStatus.FAILED
                    results[task.id] = ExecutionStatus.FAILED
                    failed.add(task.id)
                    self._sync_scheduled_copy(task)
                    progressed = True
                    continue
                unmet = [d for d in task.dependencies
                         if results.get(d) is not ExecutionStatus.COMPLETED]
                if unmet:
                    continue  # ليست جاهزة بعد — قد تكملها دورة تالية
                self._invoke_original(core, task, results, failed)
                self._sync_scheduled_copy(task)
                progressed = True
            pending = [t for t in pending if t.id not in results]
            if not pending or not progressed:
                break

        # ما تبقى بعد توقف التقدم: تبعية فاشلة (أو دورة مستحيلة) — فشل صريح لا صمت
        for task in pending:
            blocked = [d for d in task.dependencies
                       if results.get(d) is not ExecutionStatus.COMPLETED]
            if not blocked:
                task.error = "لم تُجدول"
            elif results.get(blocked[0]) is ExecutionStatus.FAILED:
                task.error = f"تبعية فاشلة: {blocked[0]}"
            else:
                task.error = f"تبعية لم تكتمل: {blocked[0]}"
            task.status = ExecutionStatus.FAILED
            results[task.id] = ExecutionStatus.FAILED
            failed.add(task.id)
            self._sync_scheduled_copy(task)

        return results

    def _sync_scheduled_copy(self, original: ExecutionTask) -> None:
        """مزامنة نسخة المجدول (المرجع الداخلي لـget_stats) مع نتيجة الأصل —
        الحالة والحقول الزمنية والنتيجة والخطأ، بعد جميع مسارات الخروج."""
        copy = self.scheduler.tasks.get(original.id)
        if copy is not None:
            copy.status = original.status
            copy.result = original.result
            copy.error = original.error
            copy.started_at = original.started_at
            copy.completed_at = original.completed_at

    def execute_pipeline(self, tasks: List[ExecutionTask]) -> Dict[str, ExecutionStatus]:
        """وضع الأنبوب (ADR-0008 — R-W1-003): تسلسل صادق عبر النواة المشتركة —
        مخرج كل مهمة على أصلها، والتبعية الفاشلة تمنع التابعة، وغياب func فشل
        صريح. لا ادعاء إكمال بلا استدعاء."""
        from agos_kernel.execution.engine import get_engine
        core = get_engine()
        by_id = {t.id: t for t in tasks}
        results: Dict[str, ExecutionStatus] = {}
        failed: set = set()

        # إعادة ضبط حقول المحاولة موحدة — حتى لمهام سجلها execute سابقاً
        for task in tasks:
            self._begin_attempt(task)

        for task in tasks:
            if task.id in results:
                continue
            # تحقق إيجابي قبل استدعاء العمل: كل تبعية يجب أن تكون اكتملت بنجاح
            # **في نطاق هذا الاستدعاء** — وجودها في by_id أو غيابها من failed
            # لا يكفي؛ فالتابعة التي تمر قبل سابقتها لا تعمل.
            missing = [d for d in task.dependencies if d not in by_id]
            unmet = [d for d in task.dependencies
                     if results.get(d) is not ExecutionStatus.COMPLETED]
            if missing or unmet:
                if missing:
                    task.error = f"تبعية غير متاحة: {missing[0]}"
                else:
                    task.error = f"تبعية لم تكتمل: {unmet[0]}"
                task.status = ExecutionStatus.FAILED
                results[task.id] = ExecutionStatus.FAILED
                failed.add(task.id)
                self._sync_scheduled_copy(task)
                continue
            self._invoke_original(core, task, results, failed)
            self._sync_scheduled_copy(task)

        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_tasks": len(self.scheduler.tasks),
            "pending_tasks": sum(1 for t in self.scheduler.tasks.values() if t.status == ExecutionStatus.PENDING),
            "completed_tasks": sum(1 for t in self.scheduler.tasks.values() if t.status == ExecutionStatus.COMPLETED),
            "failed_tasks": sum(1 for t in self.scheduler.tasks.values() if t.status == ExecutionStatus.FAILED),
        }
    
    def _generate_id(self, name: str) -> str:
        """Generate unique ID."""
        unique = f"{name}-{uuid.uuid4().hex[:8]}"
        return hashlib.md5(unique.encode()).hexdigest()[:16]
