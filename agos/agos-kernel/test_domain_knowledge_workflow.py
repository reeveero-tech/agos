#!/usr/bin/env python3
"""Test script for Domain, Knowledge, and Workflow Programs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from domains.base import Domain, DomainRegistry
from domains.software import get_domain as get_software_domain
from domains.engineering import get_domain as get_engineering_domain
from knowledge.base import KnowledgeBase, get_knowledge_base
from workflows.library import WorkflowLibrary, get_library


def test_domains():
    """Test domains."""
    print("=" * 60)
    print("Testing Domains 1-25")
    print("=" * 60)
    
    # Test Software Engineering Domain
    software = get_software_domain("software")
    print(f"✓ Domain-001: {software.metadata.name}")
    print(f"  Capabilities: {len(software.capabilities)}")
    print(f"  Knowledge Packs: {len(software.knowledge_packs)}")
    print(f"  Policies: {len(software.policies)}")
    print(f"  Workflows: {len(software.workflows)}")
    # R-Q-001: النطاق حقيقي — مكوناته الأربعة معلنة فعلاً لا صفرية
    assert software.metadata.name == "SoftwareEngineering"
    assert len(software.capabilities) > 0, "no capabilities"
    assert len(software.knowledge_packs) > 0, "no knowledge packs"
    assert len(software.policies) > 0, "no policies"
    assert len(software.workflows) > 0, "no workflows"
    
    # Test Backend Engineering Domain
    backend = get_software_domain("backend")
    print(f"✓ Domain-002: {backend.metadata.name}")
    assert backend.metadata.name == "BackendEngineering"    # R-Q-001
    
    # Test DevOps Domain
    devops = get_software_domain("devops")
    print(f"✓ Domain-006: {devops.metadata.name}")
    assert devops.metadata.name == "DevOpsEngineering"
    
    # Test SRE Domain
    sre = get_software_domain("sre")
    print(f"✓ Domain-010: {sre.metadata.name}")
    assert sre.metadata.name != ""
    
    # Test Cyber Security Domain
    security = get_engineering_domain("security")
    print(f"✓ Domain-011: {security.metadata.name}")
    assert security.metadata.name == "CyberSecurity"
    
    # Test AI Engineering Domain
    ai = get_engineering_domain("ai")
    print(f"✓ Domain-014: {ai.metadata.name}")
    assert ai.metadata.name != ""
    
    # Test LLM Engineering Domain
    llm = get_engineering_domain("llm")
    print(f"✓ Domain-016: {llm.metadata.name}")
    assert llm.metadata.name != ""
    
    # Test QA Domain
    qa = get_engineering_domain("qa")
    print(f"✓ Domain-021: {qa.metadata.name}")
    assert qa.metadata.name != ""
    
    # Test Knowledge Engineering Domain
    knowledge_eng = get_engineering_domain("knowledge")
    print(f"✓ Domain-025: {knowledge_eng.metadata.name}")
    assert knowledge_eng.metadata.name != ""
    
    print(f"\nTotal domains available: 25")


def test_knowledge():
    """Test knowledge base."""
    print("\n" + "=" * 60)
    print("Testing Knowledge Base")
    print("=" * 60)
    
    kb = get_knowledge_base()
    print(f"✓ Knowledge Base initialized")
    print(f"  Total objects: {len(kb.objects)}")
    # R-Q-001: قاعدة معرفية معلنة — الرصيد الفعلي 20 كائناً
    assert len(kb.objects) == 20, len(kb.objects)
    
    # Search test
    results = kb.search("architecture")
    print(f"  Search 'architecture': {len(results)} results")
    assert len(results) == 5, len(results)          # نتائج معلنة لا صفراً صامتاً
    
    # List by category
    arch_patterns = kb.list_by_category("architecture")
    print(f"  Architecture patterns: {len(arch_patterns)}")
    design_patterns = kb.list_by_category("design")
    print(f"  Design patterns: {len(design_patterns)}")
    security_patterns = kb.list_by_category("security")
    print(f"  Security patterns: {len(security_patterns)}")
    performance_patterns = kb.list_by_category("performance")
    print(f"  Performance patterns: {len(performance_patterns)}")
    # R-Q-001: كل تصنيف غير فارغ فعلاً
    assert len(arch_patterns) == 5, len(arch_patterns)
    assert len(design_patterns) == 5, len(design_patterns)
    assert len(security_patterns) == 3, len(security_patterns)
    assert len(performance_patterns) == 3, len(performance_patterns)


def test_workflows():
    """Test workflow library."""
    print("\n" + "=" * 60)
    print("Testing Workflow Library")
    print("=" * 60)
    
    library = get_library()
    print(f"✓ Workflow Library initialized")
    print(f"  Total workflows: {len(library.workflows)}")
    # R-Q-001: النطاق الموثق WORKFLOW-000001..000030 = 30
    assert len(library.workflows) == 30, len(library.workflows)
    
    # List workflows
    for i, (name, workflow) in enumerate(list(library.workflows.items())[:10]):
        print(f"  {i+1}. {workflow.metadata.name}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد سير العمل نفسه
        assert workflow.metadata.name, (name, workflow.metadata.name)
        assert library.get(name) is workflow
    
    print(f"  ... and {len(library.workflows) - 10} more")
    
    # Execute a workflow
    execution = library.execute("repository_analysis", {"repo": "test"})
    print(f"\n✓ Executed: {execution.workflow_id}")
    print(f"  Status: {execution.status.value}")
    print(f"  Steps completed: {len(execution.results)}")
    # R-Q-001: التنفيذ الفعلي — معرف وحالة معلنة (الخطوات 0 لمدخل زائف — صادق لا مُخفى)
    assert isinstance(execution.workflow_id, str) and execution.workflow_id.startswith("workflow-"), execution.workflow_id
    assert execution.status.value == "completed", execution.status.value


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS DOMAIN, KNOWLEDGE & WORKFLOW PROGRAMS")
    print("DOMAIN-000001 to DOMAIN-000025")
    print("KNOWLEDGE-000001 to KNOWLEDGE-000050")
    print("WORKFLOW-000001 to WORKFLOW-000030")
    print("=" * 60)
    
    test_domains()
    test_knowledge()
    test_workflows()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()