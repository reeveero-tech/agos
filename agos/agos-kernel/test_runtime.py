#!/usr/bin/env python3
"""Test script for Universal Runtime Platform."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from runtime import (
    UniversalRuntimePlatform, WorkspaceType, SessionType, ArtifactType,
    EnvironmentType, ResourceType, ScheduleType, QueueType, StateType, RecoveryType
)

def test_workspace():
    """Test workspace runtime."""
    print("=" * 60)
    print("Testing Workspace Runtime")
    print("=" * 60)
    
    platform = UniversalRuntimePlatform()
    
    # Create workspace
    workspace = platform.workspace.create_workspace(
        name="test-workspace",
        workspace_type=WorkspaceType.MISSION,
        mission_id="mission-001"
    )
    print(f"✓ Workspace created: {workspace.id}")
    print(f"  Name: {workspace.name}")
    print(f"  Status: {workspace.status.value}")
    # R-Q-001: مساحة عمل جاهزة فعلاً بالاسم المطلوب
    assert workspace.name == "test-workspace", workspace.name
    assert workspace.status.value == "ready", workspace.status.value
    
    # Clone workspace
    clone = platform.workspace.clone_workspace(workspace.id, "cloned-workspace")
    print(f"✓ Workspace cloned: {clone.id}")
    assert clone.id != workspace.id and clone.name == "cloned-workspace"   # R-Q-001
    
    # Snapshot
    snapshot = platform.workspace.snapshot_workspace(workspace.id)
    print(f"✓ Snapshot created: {snapshot.id}")
    assert snapshot.id   # R-Q-001: لقطة بمعرف فعلي
    
    return platform

def test_session(platform):
    """Test session runtime."""
    print("\n" + "=" * 60)
    print("Testing Session Runtime")
    print("=" * 60)
    
    # Create session
    session = platform.session.create_session(
        name="test-session",
        session_type=SessionType.MISSION,
        mission_id="mission-001",
        workspace_id="workspace-001"
    )
    print(f"✓ Session created: {session.id}")
    print(f"  Name: {session.name}")
    print(f"  Status: {session.status.value}")
    # R-Q-001: جلسة فعالة بالاسم المطلوب
    assert session.name == "test-session", session.name
    assert session.status.value == "active", session.status.value
    
    # Add interaction
    platform.session.add_interaction(session.id, {"message": "Hello"})
    print(f"✓ Interaction added")
    assert platform.session.get_session(session.id) is not None   # R-Q-001: الجلسة متاحة بعد التفاعل
    
    return session

def test_artifact(platform):
    """Test artifact runtime."""
    print("\n" + "=" * 60)
    print("Testing Artifact Runtime")
    print("=" * 60)
    
    # Create artifact
    artifact = platform.artifact.create_artifact(
        name="test-artifact",
        artifact_type=ArtifactType.FILE,
        workspace_id="workspace-001"
    )
    print(f"✓ Artifact created: {artifact.id}")
    print(f"  Name: {artifact.name}")
    print(f"  Type: {artifact.artifact_type.value}")
    # R-Q-001: مُنتج بالاسم والنوع المطلوبين
    assert artifact.name == "test-artifact", artifact.name
    assert artifact.artifact_type.value == "file", artifact.artifact_type.value
    
    # Validate
    platform.artifact.validate_artifact(artifact.id)
    print(f"✓ Artifact validated: {artifact.status.value}")
    assert artifact.status.value == "valid", artifact.status.value   # R-Q-001
    
    return artifact

def test_environment(platform):
    """Test environment runtime."""
    print("\n" + "=" * 60)
    print("Testing Environment Runtime")
    print("=" * 60)
    
    # Create environment
    env = platform.environment.create_environment(
        name="test-env",
        environment_type=EnvironmentType.LOCAL
    )
    print(f"✓ Environment created: {env.id}")
    print(f"  Name: {env.name}")
    print(f"  Type: {env.environment_type.value}")
    # R-Q-001: بيئة محلية بالاسم المطلوب
    assert env.name == "test-env", env.name
    assert env.environment_type.value == "local", env.environment_type.value
    
    # Health check
    healthy = platform.environment.check_health(env.id)
    print(f"✓ Health check: {'healthy' if healthy else 'unhealthy'}")
    assert healthy is True   # R-Q-001: فحص صحي فعلي
    
    return env

def test_resource(platform):
    """Test resource runtime."""
    print("\n" + "=" * 60)
    print("Testing Resource Runtime")
    print("=" * 60)
    
    # Create resource
    resource = platform.resource.create_resource(
        name="cpu-cores",
        resource_type=ResourceType.CPU,
        capacity=8.0,
        unit="cores"
    )
    print(f"✓ Resource created: {resource.id}")
    print(f"  Name: {resource.name}")
    print(f"  Capacity: {resource.capacity}")
    # R-Q-001: مورد بسعة معلنة كما أُنشئ
    assert resource.name == "cpu-cores" and resource.capacity == 8.0
    
    # Allocate
    alloc = platform.resource.allocate(resource.id, 4.0, "workspace-001")
    print(f"✓ Resource allocated: {alloc.id}")
    assert alloc.id   # R-Q-001: حجز بمعرف فعلي
    
    return resource

def test_scheduler(platform):
    """Test scheduler runtime."""
    print("\n" + "=" * 60)
    print("Testing Scheduler Runtime")
    print("=" * 60)
    
    # Create schedule
    schedule = platform.scheduler.create_schedule(
        name="test-schedule",
        schedule_type=ScheduleType.RECURRING,
        is_recurring=True,
        interval_seconds=3600
    )
    print(f"✓ Schedule created: {schedule.id}")
    print(f"  Name: {schedule.name}")
    print(f"  Type: {schedule.schedule_type.value}")
    # R-Q-001: جدول متكرر كما طُلب
    assert schedule.name == "test-schedule", schedule.name
    assert schedule.schedule_type.value == "recurring", schedule.schedule_type.value
    
    return schedule

def test_queue(platform):
    """Test queue runtime."""
    print("\n" + "=" * 60)
    print("Testing Queue Runtime")
    print("=" * 60)
    
    # Create queue
    queue = platform.queue.create_queue(
        name="test-queue",
        queue_type=QueueType.EXECUTION,
        priority_enabled=True
    )
    print(f"✓ Queue created: {queue.id}")
    print(f"  Name: {queue.name}")
    print(f"  Type: {queue.queue_type.value}")
    # R-Q-001: طابور تنفيذ بالاسم المطلوب
    assert queue.name == "test-queue", queue.name
    assert queue.queue_type.value == "execution", queue.queue_type.value
    
    # Enqueue
    item = platform.queue.enqueue(queue.id, {"task": "test"}, priority=5)
    print(f"✓ Item enqueued: {item.id}")
    assert item.id   # R-Q-001: عنصر في الطابور بمعرف فعلي
    
    return queue

def test_state(platform):
    """Test state runtime."""
    print("\n" + "=" * 60)
    print("Testing State Runtime")
    print("=" * 60)
    
    # Create state
    state = platform.state.create_state(
        name="test-state",
        state_type=StateType.MISSION,
        initial_data={"progress": 0}
    )
    print(f"✓ State created: {state.id}")
    print(f"  Name: {state.name}")
    print(f"  Version: {state.version}")
    assert state.name == "test-state" and state.version >= 1   # R-Q-001
    
    # Update
    _v_before = state.version
    platform.state.update_state(state.id, {"progress": 50})
    print(f"✓ State updated to version {state.version}")
    # R-Q-001: التحديث يرفع الإصدار ويعدّل البيانات فعلاً
    assert state.version > _v_before, state.version
    assert state.data.get("progress") == 50, state.data
    
    return state

def test_recovery(platform):
    """Test recovery runtime."""
    print("\n" + "=" * 60)
    print("Testing Recovery Runtime")
    print("=" * 60)
    
    # Create checkpoint
    checkpoint = platform.recovery.create_checkpoint(
        entity_type="workspace",
        entity_id="workspace-001",
        data={"name": "test", "status": "running"}
    )
    print(f"✓ Checkpoint created: {checkpoint.id}")
    assert checkpoint.id   # R-Q-001: نقطة حفظ بمعرف فعلي
    
    # Analyze failure
    analysis = platform.recovery.analyze_failure(
        entity_id="workspace-001",
        error_type="timeout",
        error_message="Connection timeout"
    )
    print(f"✓ Failure analyzed: {analysis.root_cause}")
    assert analysis.root_cause, "empty root cause"   # R-Q-001: تحليل بحصيلة معلنة
    
    return checkpoint

def test_platform():
    """Test the unified platform."""
    print("\n" + "=" * 60)
    print("Testing Universal Runtime Platform")
    print("=" * 60)
    
    platform = UniversalRuntimePlatform()
    
    # Create mission workspace
    workspace = platform.create_mission_workspace("mission-001", "mission-workspace")
    print(f"✓ Mission workspace created: {workspace.id}")
    assert workspace.id and workspace.name == "mission-workspace"   # R-Q-001
    
    # Create checkpoint
    checkpoint = platform.create_checkpoint_for_workspace(workspace.id)
    print(f"✓ Checkpoint created: {checkpoint.id}")
    assert checkpoint.id   # R-Q-001
    
    # Health check
    health = platform.health_check()
    print(f"✓ Platform health: {health['status']}")
    print(f"  Subsystems healthy: {health['healthy_subsystems']}/{health['total_subsystems']}")
    # R-Q-001: كل النظم الفرعية التسعة سليمة فعلاً
    assert health["status"] == "healthy", health
    assert health["healthy_subsystems"] == health["total_subsystems"] == 9, health
    
    # Stats
    stats = platform.get_stats()
    print(f"✓ Platform stats:")
    print(f"  Workspaces: {stats.workspaces_count}")
    print(f"  Sessions: {stats.sessions_count}")
    print(f"  Artifacts: {stats.artifacts_count}")
    print(f"  Environments: {stats.environments_count}")
    print(f"  Resources: {stats.resources_count}")
    print(f"  Schedules: {stats.schedules_count}")
    print(f"  Queues: {stats.queues_count}")
    print(f"  States: {stats.states_count}")
    print(f"  Checkpoints: {stats.checkpoints_count}")
    # R-Q-001: إحصاءات فعلية — ما أُنشئ أعلاه ظهر فيها
    assert stats.workspaces_count >= 1 and stats.checkpoints_count >= 1, stats

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UNIVERSAL RUNTIME PLATFORM v1 - TEST SUITE")
    print("EXECUTION-000051 to EXECUTION-000060")
    print("=" * 60)
    
    # Test individual components
    platform = test_workspace()
    test_session(platform)
    test_artifact(platform)
    test_environment(platform)
    test_resource(platform)
    test_scheduler(platform)
    test_queue(platform)
    test_state(platform)
    test_recovery(platform)
    
    # Test unified platform
    test_platform()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
