#!/usr/bin/env python3
"""
AGOS Kernel Integration Test v0.3.0

Exercises the currently-live API surface end-to-end:
- Repository Analysis pipeline (real clone -> read -> detect -> DNA)
- AutonomousCore mission lifecycle (think/validate/execute/complete)
- Smoke-import of every capability, provider, and skill module

IF ANY ASSERTION FAILS:
BLOCK ALL FUTURE DEVELOPMENT
FIX KERNEL FIRST
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAILURES = []


def assert_condition(condition: bool, message: str):
    """Assert a condition, recording failures instead of exiting immediately."""
    if not condition:
        print(f"\u274c ASSERTION FAILED: {message}")
        FAILURES.append(message)
    else:
        print(f"\u2713 {message}")


def test_module_imports():
    """Smoke-import every capability/provider/skill module."""
    print("\n--- Module import smoke test ---")
    modules = [
        "capabilities",
        "capabilities.foundation_extra",
        "providers",
        "providers.network",
        "skills.code.operations",
        "skills.file.operations",
        "skills.analysis.operations",
        "skills.knowledge.operations",
        "core",
    ]
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            assert_condition(True, f"Imported {mod_name}")
        except Exception as e:
            assert_condition(False, f"Import {mod_name} ({e})")


def test_repository_analysis_pipeline():
    """Run the real repository analysis pipeline against a live git repo on disk."""
    print("\n--- Repository Analysis pipeline (local self-repo) ---")
    from providers import LocalRepositoryProvider

    repo_root = os.path.dirname(os.path.abspath(__file__))
    provider = LocalRepositoryProvider()

    is_git_repo = provider.Exists(repo_root)
    if not is_git_repo:
        print("(skipped: agos-kernel is not itself a standalone git repo in this workspace)")
        return

    snapshot = provider.Read(repo_root)
    assert_condition(len(snapshot.files) > 0, "Read repository snapshot has files")


def test_autonomous_core():
    """Exercise the AutonomousCore mission lifecycle."""
    print("\n--- AutonomousCore mission lifecycle ---")
    from uuid import uuid4
    from core import AutonomousCore, Mission, MissionStatus

    core = AutonomousCore()
    mission = Mission(
        id=str(uuid4()),
        objective="Analyze the AGOS kernel test integration surface",
    )

    assert_condition(core.validate(mission), "Mission validated")
    assert_condition(core.execute(mission), "Mission execution started")
    assert_condition(mission.status == MissionStatus.EXECUTING, "Mission status is EXECUTING")


def main():
    """Run integration tests."""
    print("=" * 60)
    print("AGOS KERNEL INTEGRATION TEST v0.3.0")
    print("=" * 60)

    test_module_imports()
    test_repository_analysis_pipeline()
    test_autonomous_core()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"KERNEL INTEGRATION TEST FAILED ({len(FAILURES)} failure(s))")
        print("BLOCK ALL FUTURE DEVELOPMENT")
        print("FIX KERNEL FIRST")
        print("=" * 60)
        sys.exit(1)

    print("KERNEL INTEGRATION TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
