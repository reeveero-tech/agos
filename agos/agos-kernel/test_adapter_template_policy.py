#!/usr/bin/env python3
"""Test script for Adapter, Template, and Policy Programs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from adapters.base import AdapterRegistry
from adapters.source_control.git import GitAdapter, GitHubAdapter
from adapters.packages.ecosystem import NpmAdapter, PipAdapter
from adapters.ai.models import OpenAIAdapter, OllamaAdapter
from templates.library import TemplateLibrary, get_library as get_template_library
from policies.library import PolicyLibrary, get_library as get_policy_library


def test_adapters():
    """Test adapters."""
    print("=" * 60)
    print("Testing Adapters 1-50")
    print("=" * 60)
    
    # Source Control Adapters
    git = GitAdapter()
    print(f"✓ Adapter-001: {git.metadata.name} - {git.metadata.technology}")
    print(f"  Capabilities: {git.metadata.capabilities}")
    # R-Q-001: البواني تعمل والبيانات الوصفية معلنة فعلاً
    assert git.metadata.name == "Git" and git.metadata.technology == "git"
    assert git.metadata.capabilities, "git adapter has no capabilities"
    
    github = GitHubAdapter(token="test")
    print(f"✓ Adapter-002: {github.metadata.name}")
    assert github.metadata.name == "GitHub"
    
    # Package Adapters
    npm = NpmAdapter()
    print(f"✓ Adapter-008: {npm.metadata.name}")
    assert npm.metadata.name == "npm"
    
    pip = PipAdapter()
    print(f"✓ Adapter-017: {pip.metadata.name}")
    assert pip.metadata.name == "pip"
    
    # AI Adapters
    openai = OpenAIAdapter(api_key="test")
    print(f"✓ Adapter-045: {openai.metadata.name}")
    assert openai.metadata.name == "OpenAI"
    
    ollama = OllamaAdapter()
    print(f"✓ Adapter-048: {ollama.metadata.name}")
    assert ollama.metadata.name == "Ollama"
    
    # Registry
    registry = AdapterRegistry()
    registry.register(git)
    registry.register(github)
    print(f"\n✓ Adapter Registry: {len(registry.list_all())} adapters")
    # R-Q-001: التسجيل فعلي — كل مسجل يُدرج ولا يُكرر
    assert len(registry.list_all()) == 2, registry.list_all()
    assert all(a in registry.list_all() for a in (git, github))
    
    print(f"\nTotal adapters: 50 (across all categories)")


def test_templates():
    """Test templates."""
    print("\n" + "=" * 60)
    print("Testing Templates 1-40")
    print("=" * 60)
    
    library = get_template_library()
    print(f"✓ Template Library initialized")
    print(f"  Total templates: {len(library.templates)}")
    # R-Q-001: تأكيد فعلي — الرصيد الفعلي 36 قالباً (الوثيقة تقول «1-40» — فرق موثق في سجل العمل)
    assert len(library.templates) == 36, len(library.templates)
    
    # List some templates
    for i, (name, template) in enumerate(list(library.templates.items())[:10]):
        print(f"  {i+1}. {template.metadata.name} ({template.metadata.category})")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد القالب نفسه
        assert template.metadata.name, (name, template.metadata.name)
        assert library.get(name) is template
    
    print(f"  ... and {len(library.templates) - 10} more")
    
    # Get a template
    backend = library.get("backend_service")
    if backend:
        print(f"\n✓ Template 'backend_service': {backend.metadata.description}")
    # R-Q-001: قالب backend_service موجود وله وصف معلن
    assert backend is not None, "backend_service template missing"
    assert backend.metadata.description, "backend_service has no description"


def test_policies():
    """Test policies."""
    print("\n" + "=" * 60)
    print("Testing Policies 1-50")
    print("=" * 60)
    
    library = get_policy_library()
    print(f"✓ Policy Library initialized")
    print(f"  Total policies: {len(library.policies)}")
    # R-Q-001: تأكيد فعلي — الرصيد الفعلي 48 سياسة (الوثيقة تقول «1-50» — فرق موثق في سجل العمل)
    assert len(library.policies) == 48, len(library.policies)
    
    # List policies
    for i, (name, policy) in enumerate(list(library.policies.items())[:10]):
        print(f"  {i+1}. {policy.metadata.name}: {policy.metadata.intent}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد السياسة نفسها
        assert policy.metadata.name, (name, policy.metadata.name)
        assert library.get(name) is policy
    
    print(f"  ... and {len(library.policies) - 10} more")
    
    # Validate a policy
    valid, violations = library.validate("security", {})
    print(f"\n✓ Security policy validation: valid={valid}")
    # R-Q-001: التحقق الفعلي صحيح بلا مخالفات — لا مجرد طباعة
    assert valid is True, violations
    assert violations == [], violations


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS ADAPTER, TEMPLATE & POLICY PROGRAMS")
    print("ADAPTER-000001 to ADAPTER-000050")
    print("TEMPLATE-000001 to TEMPLATE-000040")
    print("POLICY-000001 to POLICY-000050")
    print("=" * 60)
    
    test_adapters()
    test_templates()
    test_policies()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()