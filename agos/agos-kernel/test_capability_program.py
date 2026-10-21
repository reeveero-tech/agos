#!/usr/bin/env python3
"""Test script for AGOS Capability, Provider, and Skill Programs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from capabilities.base import Capability, CapabilityStatus
from capabilities.repository.discovery import RepositoryDiscoveryCapability
from capabilities.repository.clone import RepositoryCloneCapability
from capabilities.repository.sync import RepositorySyncCapability, RepositoryFingerprintCapability, RepositoryStructureCapability
from capabilities.technology.detection import TechnologyDetectionCapability
from capabilities.analysis.dependency import (
    DependencyAnalysisCapability, CodeIndexingCapability,
    ArchitectureExtractionCapability, ArchitectureValidationCapability,
    PatternDetectionCapability, AntiPatternDetectionCapability, DeadCodeDetectionCapability
)

from providers.base import Provider, ProviderStatus
from providers.filesystem import FilesystemProvider, GitProvider, GitHubProvider, get_provider

from skills.base import Skill, SkillStatus
from skills.vcs.operations import CloneRepositorySkill, PullRepositorySkill, CheckoutBranchSkill
from skills.file.operations import ReadFileSkill, WriteFileSkill, SearchFilesSkill
from skills.execution.operations import ExecuteCLISkill, RunTestsSkill


def test_capabilities():
    """Test capabilities."""
    print("=" * 60)
    print("Testing Capabilities")
    print("=" * 60)
    
    # Repository Discovery
    disc = RepositoryDiscoveryCapability()
    repos = disc.execute("local")
    print(f"✓ Repository Discovery: {len(repos)} repositories")
    assert len(repos) >= 1, "no repositories discovered"   # R-Q-001
    
    # Repository Clone
    clone = RepositoryCloneCapability()
    result = clone.execute("https://github.com/example/repo", method="https")
    print(f"✓ Repository Clone: {result.success}")
    assert result.success is True, getattr(result, "error", "")  # R-Q-001
    assert result.path, "clone returned no path"
    clone.cleanup(result.path)
    
    # Repository Sync
    sync = RepositorySyncCapability()
    sync_result = sync.execute("repo-123", "pull")
    print(f"✓ Repository Sync: {sync_result.success}")
    assert sync_result.success is True   # R-Q-001
    
    # Repository Fingerprint
    fingerprint = RepositoryFingerprintCapability()
    fp = fingerprint.execute("/path/to/repo")
    print(f"✓ Repository Fingerprint: {fp.hash[:16]}...")
    assert isinstance(fp.hash, str) and len(fp.hash) >= 16, fp.hash   # R-Q-001
    
    # Repository Structure
    structure = RepositoryStructureCapability()
    struct = structure.execute("/path/to/repo")
    print(f"✓ Repository Structure: {struct.id}")
    assert struct.id, "structure returned no id"   # R-Q-001
    
    # Technology Detection
    tech = TechnologyDetectionCapability()
    detection = tech.execute(["main.py", "requirements.txt", "setup.py", "Dockerfile"])
    print(f"✓ Technology Detection: {detection.languages}")
    assert "Python" in detection.languages, detection.languages   # R-Q-001
    
    # Dependency Analysis
    dep = DependencyAnalysisCapability()
    dep_result = dep.execute([{"name": "requests", "version": "2.28", "internal": False}])
    print(f"✓ Dependency Analysis: {len(dep_result.external_deps)} deps")
    # R-Q-001: الاعتماد الخارجي المُدخل ظهر في النتيجة فعلاً
    assert len(dep_result.external_deps) == 1, dep_result.external_deps
    assert dep_result.external_deps[0].name == "requests"
    
    # Code Indexing
    idx = CodeIndexingCapability()
    index = idx.execute(["main.py", "utils.py"])
    print(f"✓ Code Indexing: {index.total_symbols} symbols")
    assert index.total_symbols >= 1, index.total_symbols   # R-Q-001
    
    # Architecture Extraction
    arch = ArchitectureExtractionCapability()
    model = arch.execute({})
    print(f"✓ Architecture Extraction: {len(model.layers)} layers")
    assert len(model.layers) > 0, "no layers extracted"   # R-Q-001
    
    # Architecture Validation
    validator = ArchitectureValidationCapability()
    validation = validator.execute({}, [])
    print(f"✓ Architecture Validation: passed={validation.passed}")
    assert validation.passed is True, validation   # R-Q-001
    
    # Pattern Detection
    patterns = PatternDetectionCapability()
    matches = patterns.execute(["main.py"])
    print(f"✓ Pattern Detection: {len(matches)} patterns")
    assert isinstance(matches, list), type(matches)   # R-Q-001
    
    # Anti-Pattern Detection
    anti = AntiPatternDetectionCapability()
    issues = anti.execute(["main.py"])
    print(f"✓ Anti-Pattern Detection: {len(issues)} issues")
    assert isinstance(issues, list), type(issues)   # R-Q-001
    
    # Dead Code Detection
    dead = DeadCodeDetectionCapability()
    dead_code = dead.execute({})
    print(f"✓ Dead Code Detection: {len(dead_code)} dead code items")
    assert hasattr(dead_code, "__len__"), type(dead_code)   # R-Q-001


def test_providers():
    """Test providers."""
    print("\n" + "=" * 60)
    print("Testing Providers")
    print("=" * 60)
    
    # Filesystem Provider
    fs = FilesystemProvider()
    health = fs.health_check()
    print(f"✓ Filesystem Provider: healthy={health['healthy']}")
    assert health["healthy"] is True, health   # R-Q-001
    
    # Git Provider
    git = GitProvider()
    git_health = git.health_check()
    print(f"✓ Git Provider: healthy={git_health['healthy']}")
    assert git_health["healthy"] is True, git_health   # R-Q-001
    
    # GitHub Provider
    gh = GitHubProvider(token="test-token")
    gh_health = gh.health_check()
    print(f"✓ GitHub Provider: authenticated={gh_health['authenticated']}")
    assert gh_health["authenticated"] is True, gh_health   # R-Q-001
    
    # Get provider
    provider = get_provider("filesystem")
    print(f"✓ Provider Registry: {provider.metadata.name}")
    assert provider.metadata.name == "Filesystem"   # R-Q-001


def test_skills():
    """Test skills."""
    print("\n" + "=" * 60)
    print("Testing Skills")
    print("=" * 60)
    
    # Clone Repository
    clone = CloneRepositorySkill()
    result = clone.execute({"url": "https://github.com/example/repo", "path": "/tmp/repo"})
    print(f"✓ CloneRepository Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Pull Repository
    pull = PullRepositorySkill()
    result = pull.execute({"path": "/tmp/repo"})
    print(f"✓ PullRepository Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Checkout Branch
    checkout = CheckoutBranchSkill()
    result = checkout.execute({"branch": "main", "path": "/tmp/repo"})
    print(f"✓ CheckoutBranch Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Read File
    read = ReadFileSkill()
    result = read.execute({"path": "/etc/hostname"})
    print(f"✓ ReadFile Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Write File
    write = WriteFileSkill()
    result = write.execute({"path": "/tmp/test.txt", "content": "Hello World"})
    print(f"✓ WriteFile Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Search Files
    search = SearchFilesSkill()
    result = search.execute({"root": "/tmp", "pattern": "test"})
    print(f"✓ SearchFiles Skill: {len(result['matches'])} matches")
    assert len(result["matches"]) > 0, result   # R-Q-001: مطابقات فعلية لا قائمة فارغة
    
    # Execute CLI
    exec_cli = ExecuteCLISkill()
    result = exec_cli.execute({"command": "echo 'Hello'"})
    print(f"✓ ExecuteCLI Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001
    
    # Run Tests
    tests = RunTestsSkill()
    result = tests.execute({"cwd": "/workspace", "framework": "pytest"})
    print(f"✓ RunTests Skill: success={result['success']}")
    assert result['success'] is True, result   # R-Q-001


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS FOUNDATION CAPABILITY PROGRAM")
    print("CAPABILITY-000001 to CAPABILITY-000020")
    print("PROVIDER-000001 to PROVIDER-000015")
    print("SKILL-000001 to SKILL-000040")
    print("=" * 60)
    
    test_capabilities()
    test_providers()
    test_skills()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print("\nAGOS Foundation Programs Ready!")


if __name__ == "__main__":
    main()