#!/usr/bin/env python3
"""Test script for Civilization Runtime."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

# R-F-005: kernel packages sharing a name with agos/<name> are imported via agos_kernel

from agos_kernel.execution import MissionCompiler, GraphRuntime, ParallelExecutor
from agos_kernel.execution import NodeType, EdgeType
from verification import VerificationRuntime, VerificationType
from approval import ApprovalRuntime, ApprovalSource
from collaboration import HumanRuntime, CollaborationAction
from organization import OrganizationRuntime, OrganizationType
from agos_kernel.governance import GovernanceRuntime, GovernanceDomain
from trust import TrustRuntime, TrustLevel
from agos_kernel.civilization import get_civilization


def test_mission_compiler():
    """Test Mission Compiler."""
    print("=" * 60)
    print("Testing Mission Compiler")
    print("=" * 60)
    
    compiler = MissionCompiler()
    
    # Compile a mission
    mission = compiler.compile(
        intent_text="Build a universal platform",
        context={"domain": "engineering"},
    )
    
    print(f"✓ Mission compiled: {mission.id}")
    print(f"  Phases: {len(mission.phases)}")
    print(f"  Goals: {len(mission.goals)}")
    print(f"  Status: {mission.status.value}")
    # R-Q-001: مهمة مصنفة فعلاً — مراحل وأهداف وحالة معلنة
    assert mission.id, "no mission id"
    assert len(mission.phases) == 10, len(mission.phases)
    assert len(mission.goals) >= 1, mission.goals
    assert mission.status.value == "completed", mission.status.value
    
    return compiler


def test_execution_graph():
    """Test Execution Graph."""
    print("\n" + "=" * 60)
    print("Testing Execution Graph")
    print("=" * 60)
    
    runtime = GraphRuntime()
    
    # Create graph
    graph = runtime.create_graph("Test Graph")
    print(f"✓ Graph created: {graph.id}")
    assert graph.id   # R-Q-001
    
    # Add nodes
    runtime.add_node(graph.id, "start", NodeType.MISSION)
    runtime.add_node(graph.id, "execute", NodeType.CAPABILITY)
    runtime.add_node(graph.id, "validate", NodeType.VALIDATION)
    print(f"✓ Nodes added: {len(graph.nodes)}")
    assert len(graph.nodes) == 3, graph.nodes   # R-Q-001
    
    # Add edges
    runtime.add_edge(graph.id, "start", "execute", EdgeType.DEPENDS_ON)
    runtime.add_edge(graph.id, "execute", "validate", EdgeType.PRODUCES)
    print(f"✓ Edges added: {len(graph.edges)}")
    assert len(graph.edges) == 2, graph.edges   # R-Q-001
    
    # Get parallel groups
    groups = runtime.get_parallel_groups(graph.id)
    print(f"✓ Parallel groups: {len(groups)}")
    assert len(groups) == 1, groups   # R-Q-001: سلسلة تبعية واحدة
    
    return runtime


def test_parallel_executor():
    """Test Parallel Execution."""
    print("\n" + "=" * 60)
    print("Testing Parallel Execution")
    print("=" * 60)
    
    executor = ParallelExecutor(max_workers=5)
    
    # Create tasks — ADR-0008 (R-W1-003): عمل حقيقي قابل للاستدعاء (غياب func
    # فشل صريح لا نجاح) — السلسلة تظل تختبر عقد التبعيات نفسه
    tasks = []
    for i in range(3):
        from agos_kernel.execution.parallel import ExecutionTask
        task = ExecutionTask(
            id=f"task-{i}",
            name=f"Task {i}",
            func=lambda tag: f"done-{tag}",
            args=(f"task-{i}",),
            dependencies=[] if i == 0 else [f"task-{i-1}"],
        )
        tasks.append(task)
    
    # Execute
    results = executor.execute(tasks)
    print(f"✓ Tasks executed: {len(results)}")
    
    # Stats
    stats = executor.get_stats()
    print(f"✓ Stats: {stats}")
    # R-Q-001: عقد execute(): تحليل التبعيات ثم تنفيذ كل الدفعات — السلسلة تكتمل كلها.
    # (كشف هذا الاختبار خللاً حقيقياً: add_task كان يولّد معرفات جديدة فتشير التبعيات
    # لمعرفات لا تكتمل أبداً — صُلح في parallel.py بمعرف المهمة الأصلية.)
    assert stats["total_tasks"] == 3, stats
    assert stats["failed_tasks"] == 0, stats
    assert stats["pending_tasks"] == 0, stats
    assert stats["completed_tasks"] == 3, stats
    # والقيمة المعادة نفسها: كل المهام الأصلية بحالة مكتملة — لا معرفات وهمية
    assert set(results) == {t.id for t in tasks}, results
    assert all(status.value == "completed" for status in results.values()), results
    
    return executor


def test_verification():
    """Test Verification."""
    print("\n" + "=" * 60)
    print("Testing Verification")
    print("=" * 60)
    
    runtime = VerificationRuntime()
    
    # Verify artifact
    report = runtime.verify(
        artifact_id="test-artifact",
        artifact_data={"name": "test"},
    )
    
    print(f"✓ Verification completed")
    print(f"  Results: {len(report.results)}")
    print(f"  Passed: {report.overall_passed}")
    # R-Q-001: تحقق فعلي — نتائج معلنة وناجحة
    assert len(report.results) == 8, len(report.results)
    assert report.overall_passed is True, report.overall_passed
    
    return runtime


def test_approval():
    """Test Approval."""
    print("\n" + "=" * 60)
    print("Testing Approval")
    print("=" * 60)
    
    runtime = ApprovalRuntime()
    
    # Create request
    request = runtime.create_request(
        request_type="deployment",
        description="Deploy to production",
        source=ApprovalSource.AUTOMATIC,
    )
    
    print(f"✓ Approval request created: {request.id}")
    assert request.id   # R-Q-001
    
    # Approve
    runtime.approve(request.id, "admin", "Approved")
    print(f"✓ Request approved")
    # R-Q-001: الاعتماد انعكس فعلاً على حالة الطلب
    assert runtime.get_request(request.id).status.value == "approved"
    
    return runtime


def test_collaboration():
    """Test Human Collaboration."""
    print("\n" + "=" * 60)
    print("Testing Human Collaboration")
    print("=" * 60)
    
    runtime = HumanRuntime()
    
    # Add contribution
    contribution = runtime.add_contribution(
        action=CollaborationAction.REVIEW,
        contributor_id="user-1",
        content="Code review feedback",
    )
    
    print(f"✓ Contribution added: {contribution.id}")
    assert contribution.id   # R-Q-001
    
    # Create review
    review = runtime.create_review(
        target_id="pr-123",
        target_type="pull_request",
        reviewer_id="user-1",
    )
    
    print(f"✓ Review created: {review.id}")
    # R-Q-001: مراجعة معلنة بحالة صريحة
    assert review.id and review.status.value == "pending", review.status.value
    
    return runtime


def test_organization():
    """Test Organization."""
    print("\n" + "=" * 60)
    print("Testing Organization")
    print("=" * 60)
    
    runtime = OrganizationRuntime()
    
    # Create organization
    org = runtime.create_organization(
        name="Engineering",
        org_type=OrganizationType.DEPARTMENT,
        description="Engineering department",
    )
    
    print(f"✓ Organization created: {org.id}")
    print(f"  Name: {org.name}")
    assert org.id and org.name == "Engineering"   # R-Q-001
    
    return runtime


def test_governance():
    """Test Governance."""
    print("\n" + "=" * 60)
    print("Testing Governance")
    print("=" * 60)
    
    runtime = GovernanceRuntime()
    
    # Create rule
    rule = runtime.create_rule(
        name="Security Check",
        domain=GovernanceDomain.SECURITY,
        description="All deployments must pass security check",
        severity="error",
    )
    
    print(f"✓ Governance rule created: {rule.id}")
    # R-Q-001: قاعدة بالاسم والنطاق المطلوبين
    assert rule.id and rule.domain.value == "security", rule.domain
    
    # Check compliance
    result = runtime.check_compliance(
        entity_id="test-entity",
        entity_type="deployment",
    )
    
    print(f"✓ Compliance checked: {result['compliant']}")
    # R-Q-001 (منقّح — R-W1-007/ADR-0010): القاعدة بلا مواصفة تنفيذية لا
    # تُحتسب مخالفة بلا فحص ولا يُعلن امتثال بلا فحص — حكم unverified معلل
    # (كانت تُحتسب مخالفة تلقائياً بseverity="error" — عدّل التوقع بلا
    # حذف الاسم)
    assert result["compliant"] is False, result
    assert result["violations"] == [], result["violations"]
    assert len(result["unverified"]) == 1, result["unverified"]
    assert result["unverified"][0]["rule_name"] == "Security Check"
    
    return runtime


def test_trust():
    """Test Trust."""
    print("\n" + "=" * 60)
    print("Testing Trust")
    print("=" * 60)
    
    runtime = TrustRuntime()
    
    # Create trust score
    score = runtime.create_trust_score(
        entity_id="test-entity",
        entity_type="artifact",
        factors={
            "verification": 0.9,
            "evidence": 0.8,
            "history": 0.7,
        },
    )
    
    print(f"✓ Trust score created: {score.overall_score:.2f}")
    print(f"  Level: {score.trust_level.value}")
    # R-Q-001: درجة ثقة محسوبة من العوامل فعلاً
    assert 0.0 < score.overall_score < 1.0, score.overall_score
    assert score.trust_level.value in ("low", "medium", "high"), score.trust_level
    
    return runtime


def test_civilization():
    """Test Civilization Runtime."""
    print("\n" + "=" * 60)
    print("Testing AGOS Autonomous Civilization Runtime v1.0")
    print("=" * 60)
    
    civilization = get_civilization()
    
    print(f"✓ Civilization initialized")
    print(f"  Version: {civilization.version}")
    print(f"  Name: {civilization.name}")
    # R-Q-001: حضارة بالاسم والإصدار المعلنين
    assert civilization.version == "1.0.0" and civilization.name == "AGOS Civilization"
    
    # Compile mission
    mission = civilization.compile_mission("Build universal AI platform")
    print(f"✓ Mission compiled: {mission.id}")
    assert mission.id and mission.phases   # R-Q-001
    
    # Create execution graph
    graph = civilization.create_execution_graph("Test Graph")
    print(f"✓ Execution graph created: {graph.id}")
    assert graph.id   # R-Q-001
    
    # Verify
    report = civilization.verify("test-artifact", {"data": "test"})
    print(f"✓ Artifact verified: {report.overall_passed}")
    assert report.overall_passed is True, report   # R-Q-001
    
    # Create organization
    org = civilization.create_organization("AGOS Corp", OrganizationType.TEAM)
    print(f"✓ Organization created: {org.name}")
    assert org.name == "AGOS Corp"   # R-Q-001
    
    # Check governance
    result = civilization.check_governance("entity-1", "deployment")
    print(f"✓ Governance check: {result['compliant']}")
    # R-Q-001: نسخة الحضارة هذه بلا قواعد error مسجلة (قاعدة test_governance في
    # نسخة مستقلة أخرى) فلا مخالفات — العقد من runtime.py محفوظ
    assert result["compliant"] is True, result
    assert result["violations"] == [], result
    
    # Assess trust
    score = civilization.assess_trust("artifact-1", "artifact")
    print(f"✓ Trust assessed: {score.overall_score:.2f}")
    assert 0.0 <= score.overall_score <= 1.0, score   # R-Q-001
    
    # Get stats
    stats = civilization.get_stats()
    print(f"\n✓ Civilization Stats:")
    print(f"  Missions compiled: {stats['metrics']['missions_compiled']}")
    print(f"  Graphs created: {stats['metrics']['graphs_created']}")
    print(f"  Verifications run: {stats['metrics']['verifications_run']}")
    # R-Q-001: ما نُفذ أعلاه محسوب فعلاً في المقاييس
    assert stats["metrics"]["missions_compiled"] == 1, stats
    assert stats["metrics"]["graphs_created"] == 1, stats
    assert stats["metrics"]["verifications_run"] == 1, stats
    
    # Health check
    health = civilization.health_check()
    print(f"\n✓ Health: {health['status']}")
    assert health["status"] == "healthy", health   # R-Q-001
    
    return civilization


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS CIVILIZATION RUNTIME - TEST SUITE")
    print("EXECUTION-000071 to EXECUTION-000080")
    print("=" * 60)
    
    # Test subsystems
    test_mission_compiler()
    test_execution_graph()
    test_parallel_executor()
    test_verification()
    test_approval()
    test_collaboration()
    test_organization()
    test_governance()
    test_trust()
    
    # Test civilization
    test_civilization()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nAGOS Autonomous Civilization Runtime v1.0 Ready!")


if __name__ == "__main__":
    main()
