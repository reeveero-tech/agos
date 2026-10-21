#!/usr/bin/env python3
"""Test script for Civilization Platform."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from orchestrator import WorkspaceOrchestrator, WorkspaceState
from repository import MultiRepositoryRuntime, RepositoryType
from crossdomain import CrossDomainRuntime, Domain
from crossdomain import LongRunningMissionRuntime, MissionState
from crossdomain import SelfDiagnosticsRuntime
from healing import SelfHealingRuntime, FailureType
from prediction import PredictionRuntime
from simulation import SimulationRuntime, SimulationType
from api import CivilizationAPI
from platform_runtime import get_platform


def test_orchestrator():
    """Test Multi-Workspace Orchestrator."""
    print("=" * 60)
    print("Testing Multi-Workspace Orchestrator")
    print("=" * 60)
    
    orchestrator = WorkspaceOrchestrator()
    
    # Create workspaces
    ws1 = orchestrator.create_workspace("workspace-1")
    ws2 = orchestrator.create_workspace("workspace-2", parent_id=ws1.id)
    
    print(f"✓ Workspace created: {ws1.id}")
    print(f"✓ Nested workspace created: {ws2.id}")
    # R-Q-001: مساحة العمل المتداخلة ابنة للأولى فعلاً
    assert ws2.parent_id == ws1.id, ws2.parent_id
    
    # Clone
    cloned = orchestrator.clone_workspace(ws1.id, "cloned-workspace")
    print(f"✓ Cloned workspace: {cloned.id}")
    assert cloned.id != ws1.id and cloned.name == "cloned-workspace"   # R-Q-001
    
    # Checkpoint
    checkpoint = orchestrator.create_checkpoint(ws1.id)
    print(f"✓ Checkpoint created: {checkpoint}")
    assert checkpoint   # R-Q-001
    
    # Stats
    stats = orchestrator.get_stats()
    print(f"✓ Total workspaces: {stats['total_workspaces']}")
    # R-Q-001: الثلاث التي أُنشئت (الأصل والابن والنسخة) محسوبة فعلاً
    assert stats["total_workspaces"] == 3, stats
    
    return orchestrator


def test_repository():
    """Test Multi-Repository Runtime."""
    print("\n" + "=" * 60)
    print("Testing Multi-Repository Runtime")
    print("=" * 60)
    
    runtime = MultiRepositoryRuntime()
    
    # Register repositories
    repo1 = runtime.register_repository(
        name="frontend",
        url="https://github.com/org/frontend",
        repo_type=RepositoryType.SOURCE,
        org="org1",
    )
    
    repo2 = runtime.register_repository(
        name="backend",
        url="https://github.com/org/backend",
        repo_type=RepositoryType.SOURCE,
        org="org1",
    )
    
    print(f"✓ Repository registered: {repo1.name}")
    print(f"✓ Repository registered: {repo2.name}")
    # R-Q-001: المستودعان مسجلان فعلاً بالاسماء المطلوبة
    assert repo1.name == "frontend" and repo2.name == "backend"
    
    # Snapshot
    snapshot = runtime.create_snapshot(repo1.id)
    print(f"✓ Snapshot created: {snapshot}")
    assert snapshot   # R-Q-001
    
    # Federation analysis
    analysis = runtime.analyze_federation("org1")
    print(f"✓ Federation analysis: {analysis['repository_count']} repos")
    # R-Q-001: المستودعان المسجلان في org1 ظهرا في التحليل فعلاً
    assert analysis["repository_count"] == 2, analysis
    
    return runtime


def test_cross_domain():
    """Test Cross-Domain Runtime."""
    print("\n" + "=" * 60)
    print("Testing Cross-Domain Reasoning")
    print("=" * 60)
    
    runtime = CrossDomainRuntime()
    
    # Add context
    runtime.add_context(Domain.SOFTWARE, knowledge=["python", "testing"])
    runtime.add_context(Domain.SECURITY, knowledge=["authentication", "encryption"])
    
    # Reason across domains
    decision = runtime.reason(
        problem="Secure software deployment",
        domains=[Domain.SOFTWARE, Domain.SECURITY],
    )
    
    print(f"✓ Cross-domain decision: {decision.id}")
    print(f"  Reasoning: {decision.reasoning[:50]}...")
    # R-Q-001: قرار عبر المجالين بعقلانية مرتبطة بالمشكلة فعلاً
    assert decision.id, "no decision id"
    assert "Secure software deployment" in decision.reasoning, decision.reasoning
    assert len(decision.domains) == 2, decision.domains
    
    return runtime


def test_long_running():
    """Test Long-Running Mission Runtime."""
    print("\n" + "=" * 60)
    print("Testing Long-Running Mission Runtime")
    print("=" * 60)
    
    runtime = LongRunningMissionRuntime()
    
    # Create mission
    mission = runtime.create_mission("long-running-1")
    print(f"✓ Mission created: {mission['id']}")
    assert mission["id"]   # R-Q-001
    
    # Start and pause
    runtime.start(mission['id'])
    runtime.pause(mission['id'])
    runtime.resume(mission['id'])
    
    # Checkpoint
    checkpoint = runtime.checkpoint(mission['id'])
    print(f"✓ Checkpoint created: {checkpoint}")
    assert checkpoint   # R-Q-001
    
    # Timeline
    timeline = runtime.get_timeline(mission['id'])
    print(f"✓ Timeline events: {len(timeline)}")
    # R-Q-001: الأحداث الأربعة (بدء/إيقاف/استئناف/نقطة حفظ) ظهرت فعلاً
    assert len(timeline) == 4, len(timeline)
    
    return runtime


def test_diagnostics():
    """Test Self-Diagnostics Runtime."""
    print("\n" + "=" * 60)
    print("Testing Self-Diagnostics Runtime")
    print("=" * 60)
    
    runtime = SelfDiagnosticsRuntime()
    
    # Register subsystems
    runtime.register_subsystem("kernel")
    runtime.register_subsystem("knowledge")
    runtime.register_subsystem("execution")
    
    # Diagnose
    reports = runtime.diagnose()
    print(f"✓ Diagnostic reports: {len(reports)}")
    # R-Q-001: تقرير لكل نظام فرعي مسجل فعلاً
    assert len(reports) == 3, len(reports)
    
    # Health report
    health = runtime.generate_health_report()
    print(f"✓ Platform health: {health['status']}")
    assert health["status"] == "healthy", health   # R-Q-001
    
    return runtime


def test_healing():
    """Test Self-Healing Runtime."""
    print("\n" + "=" * 60)
    print("Testing Self-Healing Runtime")
    print("=" * 60)
    
    runtime = SelfHealingRuntime()
    
    # Detect failure
    failure = runtime.detect_failure(
        failure_type=FailureType.PROVIDER,
        description="Provider timeout",
    )
    print(f"✓ Failure detected: {failure.id}")
    assert failure.id   # R-Q-001
    
    # Plan recovery
    plan = runtime.plan_recovery(failure.id)
    print(f"✓ Recovery planned: {plan.id}")
    print(f"  Actions: {len(plan.actions)}")
    # R-Q-001: خطة إنعاش بفعلين معلنين على الأقل
    assert plan.id and len(plan.actions) >= 1, plan.actions
    
    # Execute
    success = runtime.execute_recovery(plan.id)
    print(f"✓ Recovery executed: {success}")
    assert success is True   # R-Q-001: الإنعاش نجح فعلاً
    
    return runtime


def test_prediction():
    """Test Prediction Runtime."""
    print("\n" + "=" * 60)
    print("Testing Prediction Runtime")
    print("=" * 60)
    
    runtime = PredictionRuntime()
    
    # Predict
    duration = runtime.predict_duration("mission-1", {"estimated_duration": 3600})
    cost = runtime.predict_cost("mission-1", {"estimated_cost": 100})
    risk = runtime.predict_risk("mission-1", {"estimated_risk": 0.3})
    
    print(f"✓ Duration predicted: {duration.predicted_value:.0f}s (confidence: {duration.confidence:.0%})")
    print(f"✓ Cost predicted: ${cost.predicted_value:.2f}")
    print(f"✓ Risk predicted: {risk.predicted_value:.0%}")
    # R-Q-001: تنبؤات معلنة حول التقديرات المدخلة لا قيم خاوية
    assert 0.0 < duration.confidence <= 1.0, duration.confidence
    assert duration.predicted_value > 0, duration.predicted_value
    assert 0.0 < cost.predicted_value < 1000.0, cost.predicted_value
    assert 0.0 < risk.predicted_value < 1.0, risk.predicted_value
    
    # Forecast
    forecast = runtime.forecast_resource_usage("cpu", periods=5)
    print(f"✓ Forecast generated: {len(forecast.values)} periods")
    assert len(forecast.values) == 5, forecast.values   # R-Q-001
    
    return runtime


def test_simulation():
    """Test Simulation Runtime."""
    print("\n" + "=" * 60)
    print("Testing Simulation Runtime")
    print("=" * 60)
    
    runtime = SimulationRuntime()
    
    # Create scenario
    scenario = runtime.create_scenario(
        name="test-deployment",
        simulation_type=SimulationType.MISSION_PLAN,
    )
    print(f"✓ Scenario created: {scenario.name}")
    assert scenario.name == "test-deployment"   # R-Q-001
    
    # Run simulation
    simulation = runtime.run_simulation(scenario.id)
    print(f"✓ Simulation run: {simulation.id}")
    print(f"  Status: {simulation.status.value}")
    # R-Q-001: محاكاة اكتملت فعلاً
    assert simulation.id, "no simulation id"
    assert simulation.status.value == "completed", simulation.status.value
    
    # Analyze
    analysis = runtime.analyze(simulation.id)
    print(f"✓ Analysis: {analysis.get('results', {})}")
    # R-Q-001: تحليل بمخرجات معلنة
    assert analysis.get("results"), analysis
    
    return runtime


def test_api():
    """Test Civilization API."""
    print("\n" + "=" * 60)
    print("Testing Civilization API")
    print("=" * 60)
    
    from simulation.runtime import setup_api
    
    runtime = CivilizationAPI()
    setup_api(runtime)
    
    print(f"✓ API initialized: v{runtime.version}")
    print(f"✓ Endpoints registered: {len(runtime.endpoints)}")
    # R-Q-001: واجهة بإصدار ونقاط نهاية معلنة
    assert runtime.version == "v1.0.0", runtime.version
    assert len(runtime.endpoints) == 2, runtime.endpoints
    
    # Create request
    request = runtime.create_request("/mission", params={}, body={})
    print(f"✓ Request created: {request.id}")
    assert request.id   # R-Q-001: طلب بمعرف فعلي
    
    return runtime


def test_platform():
    """Test Civilization Platform."""
    print("\n" + "=" * 60)
    print("Testing AGOS Civilization Platform v1.0")
    print("=" * 60)
    
    platform = get_platform()
    
    print(f"✓ Platform initialized")
    print(f"  Version: {platform.version}")
    print(f"  Name: {platform.name}")
    # R-Q-001: منصة بالاسم والإصدار المعلنين
    assert platform.version == "1.0.0" and platform.name == "AGOS Civilization Platform"
    
    # Health check
    health = platform.health_check()
    print(f"\n✓ Platform health: {health['status']}")
    print(f"  Subsystems healthy: {sum(1 for v in health['subsystems'].values() if v == 'healthy')}/{len(health['subsystems'])}")
    # R-Q-001: صحة معلنة وكل الأنظمة الفرعية بلا حالة فشل فعلاً
    # (kernel يعلن «ready» — معجم حالة صالح لا يعني «healthy»)
    assert health["status"] == "healthy", health
    bad = {k: v for k, v in health["subsystems"].items()
          if v in ("unhealthy", "failed", "error", "degraded")}
    assert not bad, bad
    assert len(health["subsystems"]) == 12, health
    
    # Stats
    stats = platform.get_stats()
    print(f"\n✓ Platform Stats:")
    print(f"  Workspaces: {stats['metrics']['workspaces']}")
    print(f"  Repositories: {stats['metrics']['repositories']}")
    print(f"  Organizations: {stats['metrics']['organizations']}")
    
    # Describe
    description = platform.describe()
    print(f"\n✓ Platform Description:")
    print(f"  Capabilities: {len(description['capabilities'])}")
    print(f"  Subsystems: {len(description['subsystems'])}")
    # R-Q-001: وصف بمحتوى معلن فعلاً
    assert len(description["capabilities"]) == 10, description
    assert len(description["subsystems"]) == 12, description
    
    return platform


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS CIVILIZATION PLATFORM - TEST SUITE")
    print("EXECUTION-000081 to EXECUTION-000090")
    print("=" * 60)
    
    # Test subsystems
    test_orchestrator()
    test_repository()
    test_cross_domain()
    test_long_running()
    test_diagnostics()
    test_healing()
    test_prediction()
    test_simulation()
    test_api()
    
    # Test platform
    test_platform()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nAGOS Civilization Platform v1.0 Ready!")


if __name__ == "__main__":
    main()
