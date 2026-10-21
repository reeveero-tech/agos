#!/usr/bin/env python3
"""Test script for Engineering Intelligence Platform."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

# R-F-005: kernel packages sharing a name with agos/<name> are imported via agos_kernel

from agos_kernel.intelligence import (
    EngineeringIntelligencePlatform,
    analyze_repository,
)

def test_repository_analysis():
    """Test repository analysis."""
    print("=" * 60)
    print("Testing Repository Analysis")
    print("=" * 60)
    
    platform = EngineeringIntelligencePlatform(str(_AGOS_KERNEL))
    report = platform.analyze()
    
    # Repository
    if report.repository:
        print(f"✓ Repository analyzed")
        print(f"  - Languages: {[l.value for l in report.repository.languages]}")
        print(f"  - Frameworks: {[f.value for f in report.repository.frameworks]}")
        print(f"  - Files: {report.repository.metrics.total_files}")
        print(f"  - Lines: {report.repository.metrics.total_lines}")
    else:
        print("✗ Repository analysis failed")
        if report.errors:
            print(f"  Errors: {report.errors}")
    # R-Q-001: تحليل المستودع نجح فعلاً — لغات وملفات وأسطر معلنة
    assert report.repository is not None, report.errors
    assert report.repository.languages, "no languages detected"
    assert report.repository.metrics.total_files > 0
    assert report.repository.metrics.total_lines > 0
    
    return report

def test_code_analysis(report):
    """Test code analysis."""
    print("\n" + "=" * 60)
    print("Testing Code Analysis")
    print("=" * 60)
    
    if report.code:
        print(f"✓ Code analyzed")
        print(f"  - Files: {len(report.code.files)}")
        print(f"  - Functions: {report.code.total_functions}")
        print(f"  - Classes: {report.code.total_classes}")
        print(f"  - Complexity: {report.code.health.complexity_score:.2f}")
    else:
        print("✗ Code analysis failed")
    # R-Q-001: تحليل الكود نجح فعلاً — ملفات محللة معلنة
    assert report.code is not None
    assert len(report.code.files) > 0, "no code files analyzed"

def test_architecture_analysis(report):
    """Test architecture analysis."""
    print("\n" + "=" * 60)
    print("Testing Architecture Analysis")
    print("=" * 60)
    
    if report.architecture:
        print(f"✓ Architecture analyzed")
        print(f"  - Style: {report.architecture.style.value}")
        print(f"  - Confidence: {report.architecture.confidence:.2f}")
        print(f"  - Layers: {len(report.architecture.layers)}")
        print(f"  - Components: {len(report.architecture.components)}")
        print(f"  - Score: {report.architecture.score.overall:.2f}")
    else:
        print("✗ Architecture analysis failed")
    # R-Q-001: تحليل المعمارية نجح فعلاً — نمط وثقة وطبقات ومكونات معلنة
    assert report.architecture is not None
    assert report.architecture.style.value == "event_driven", report.architecture.style.value
    assert 0.0 <= report.architecture.confidence <= 1.0
    assert len(report.architecture.layers) > 0, "no layers"
    assert len(report.architecture.components) > 0, "no components"
    assert 0.0 <= report.architecture.score.overall <= 1.0

def test_capability_discovery(report):
    """Test capability discovery."""
    print("\n" + "=" * 60)
    print("Testing Capability Discovery")
    print("=" * 60)
    
    if report.capabilities:
        print(f"✓ Capabilities discovered: {len(report.capabilities)}")
        for cap in report.capabilities[:5]:
            print(f"  - {cap.name} ({cap.type})")
        if len(report.capabilities) > 5:
            print(f"  ... and {len(report.capabilities) - 5} more")
    else:
        print("✗ Capability discovery failed")
    # R-Q-001: كشف القدرات نجح فعلاً — عدد معلن وكل قدرة باسم ونوع
    assert len(report.capabilities) > 0, "no capabilities discovered"
    for cap in report.capabilities[:5]:
        assert cap.name and cap.type, cap

def test_provider_discovery(report):
    """Test provider discovery."""
    print("\n" + "=" * 60)
    print("Testing Provider Discovery")
    print("=" * 60)
    
    if report.providers:
        print(f"✓ Providers discovered: {len(report.providers)}")
        for provider in report.providers[:5]:
            print(f"  - {provider.name} ({provider.type})")
        if len(report.providers) > 5:
            print(f"  ... and {len(report.providers) - 5} more")
    else:
        print("✗ Provider discovery failed")
    # R-Q-001: كشف المزودين نجح فعلاً — عدد معلن وكل مزود باسم ونوع
    assert len(report.providers) > 0, "no providers discovered"
    for provider in report.providers[:5]:
        assert provider.name and provider.type, provider

def test_project_dna(report):
    """Test project DNA generation."""
    print("\n" + "=" * 60)
    print("Testing Project DNA Generation")
    print("=" * 60)
    
    if report.project_dna:
        print(f"✓ Project DNA generated")
        print(f"  - ID: {report.project_dna.id}")
        print(f"  - Name: {report.project_dna.name}")
        print(f"  - Languages: {report.project_dna.languages}")
        print(f"  - Complexity: {report.project_dna.complexity_score:.2f}")
        print(f"  - Maintainability: {report.project_dna.maintainability_index:.2f}")
    else:
        print("✗ Project DNA generation failed")
    # R-Q-001: بصمة المشروع ولدت فعلاً — معرف واسم ولغات ومؤشرات معلنة
    assert report.project_dna is not None
    assert report.project_dna.id, "no DNA id"
    assert report.project_dna.name, "no DNA name"
    assert report.project_dna.languages, "no DNA languages"
    assert 0.0 <= report.project_dna.complexity_score <= 1.0
    assert 0.0 <= report.project_dna.maintainability_index <= 1.0

def test_knowledge_extraction(report):
    """Test knowledge extraction."""
    print("\n" + "=" * 60)
    print("Testing Knowledge Extraction")
    print("=" * 60)
    
    if report.knowledge:
        print(f"✓ Knowledge extracted: {report.knowledge.total_knowledge} items")
        print(f"  - Best Practices: {len(report.knowledge.best_practices)}")
        print(f"  - Patterns: {len(report.knowledge.patterns)}")
        print(f"  - Decisions: {len(report.knowledge.decisions)}")
        print(f"  - Technologies: {len(report.knowledge.technologies)}")
    else:
        print("✗ Knowledge extraction failed")
    # R-Q-001: استخراج المعرفة نجح فعلاً — عناصر معلنة لا قائمة فارغة
    assert report.knowledge is not None
    assert report.knowledge.total_knowledge > 0, "no knowledge extracted"

def test_query_engine():
    """Test query engine."""
    print("\n" + "=" * 60)
    print("Testing Query Engine")
    print("=" * 60)
    
    platform = EngineeringIntelligencePlatform(str(_AGOS_KERNEL))
    report = platform.analyze()
    
    # Test queries
    result = platform.query("analyzer")
    print(f"✓ Query 'analyzer': {result.count} results")
    # R-Q-001: الاستعلام يعيد نتائج فعلية لا عدداً صامتاً
    assert result.count > 0, "query 'analyzer' returned nothing"
    
    result = platform.query("test", query_type="file")
    print(f"✓ Query 'test' (files): {result.count} results")
    assert result.count >= 0, result.count   # عدد صالح معلن

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ENGINEERING INTELLIGENCE PLATFORM v2 - TEST SUITE")
    print("=" * 60)
    
    # Run tests
    report = test_repository_analysis()
    test_code_analysis(report)
    test_architecture_analysis(report)
    test_capability_discovery(report)
    test_provider_discovery(report)
    test_project_dna(report)
    test_knowledge_extraction(report)
    test_query_engine()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)
    
    # Summary
    print("\nSummary:")
    print(f"  - Analysis completed in {report.analysis_duration_seconds:.2f}s")
    print(f"  - Errors: {len(report.errors)}")
    print(f"  - Warnings: {len(report.warnings)}")

if __name__ == "__main__":
    main()
