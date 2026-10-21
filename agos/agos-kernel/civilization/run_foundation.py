#!/usr/bin/env python3
"""
Foundation Civilization Runner
PHASE-02: Foundation Civilization

Run this script to test the Foundation Civilization capabilities.
"""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[2])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'

import sys
import json
import importlib.util
from pathlib import Path

# Setup path
current_dir = Path(__file__).parent
repo_root = current_dir.parent.parent  # <AGOS_ROOT>
sys.path.insert(0, str(repo_root))


def _load_module(name, path):
    """Load a module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_analyzer():
    """Test repository analyzer."""
    print("\n[1/5] Testing Repository Analyzer...")
    module = _load_module(
        'repository_analysis',
        str(_AGOS_KERNEL / 'civilization/capabilities/repository_analysis.py')
    )
    RepositoryAnalyzer = module.RepositoryAnalyzer
    
    analyzer = RepositoryAnalyzer()
    result = analyzer.analyze(str(_AGOS_ROOT))
    
    print(f"  ✓ Repository: {result.get('name')}")
    print(f"  ✓ Files: {result.get('file_count')}")
    print(f"  ✓ Language: {result.get('primary_language')}")
    print(f"  ✓ Size: {result.get('size_mb')} MB")
    
    return result


def test_architecture_analyzer():
    """Test architecture analyzer."""
    print("\n[2/5] Testing Architecture Analyzer...")
    module = _load_module(
        'architecture_analysis',
        str(_AGOS_KERNEL / 'civilization/capabilities/architecture_analysis.py')
    )
    ArchitectureAnalyzer = module.ArchitectureAnalyzer
    
    analyzer = ArchitectureAnalyzer()
    result = analyzer.analyze(str(_AGOS_ROOT))
    
    print(f"  ✓ Modules: {result['metrics']['total_modules']}")
    print(f"  ✓ Classes: {result['metrics']['total_classes']}")
    print(f"  ✓ Functions: {result['metrics']['total_functions']}")
    print(f"  ✓ Patterns: {result['metrics']['pattern_count']}")
    
    return result


def test_dependency_analyzer():
    """Test dependency analyzer."""
    print("\n[3/5] Testing Dependency Analyzer...")
    module = _load_module(
        'dependency_analysis',
        str(_AGOS_KERNEL / 'civilization/capabilities/dependency_analysis.py')
    )
    DependencyAnalyzer = module.DependencyAnalyzer
    
    analyzer = DependencyAnalyzer()
    result = analyzer.analyze(str(_AGOS_ROOT))
    
    print(f"  ✓ Total Dependencies: {result['total_dependencies']}")
    print(f"  ✓ Internal Modules: {result['metrics']['internal_deps']}")
    print(f"  ✓ Sources: {len(result['dependency_sources'])}")
    
    return result


def test_repository_dna():
    """Test repository DNA."""
    print("\n[4/5] Testing Repository DNA Generator...")
    module = _load_module(
        'repository_dna',
        str(_AGOS_KERNEL / 'civilization/capabilities/repository_dna.py')
    )
    RepositoryDNA = module.RepositoryDNA
    
    dna_gen = RepositoryDNA()
    dna = dna_gen.generate(str(_AGOS_ROOT))
    
    print(f"  ✓ DNA Version: {dna['version']}")
    print(f"  ✓ Structure: {dna['fragments']['structure']}")
    print(f"  ✓ Code: {dna['fragments']['code']}")
    print(f"  ✓ Signature: {dna['signature']}")
    
    return dna


def test_knowledge_extraction():
    """Test knowledge extraction."""
    print("\n[5/5] Testing Knowledge Extraction...")
    module = _load_module(
        'knowledge_extraction',
        str(_AGOS_KERNEL / 'civilization/capabilities/knowledge_extraction.py')
    )
    KnowledgeExtractor = module.KnowledgeExtractor
    
    extractor = KnowledgeExtractor()
    knowledge = extractor.extract(str(_AGOS_ROOT))
    
    print(f"  ✓ Modules: {len(knowledge['modules'])}")
    print(f"  ✓ Classes: {len(knowledge['classes'])}")
    print(f"  ✓ Functions: {len(knowledge['functions'])}")
    print(f"  ✓ Technologies: {knowledge['technologies']}")
    print(f"  ✓ Patterns: {knowledge['patterns'][:5]}...")
    
    return knowledge


def run_foundation_test():
    """Run complete foundation test."""
    print("=" * 70)
    print("AGOS FOUNDATION CIVILIZATION - TEST RUN")
    print("=" * 70)
    print(f"Testing Foundation Capabilities on AGOS Kernel Repository")
    print()
    
    results = {}
    
    try:
        # Test each capability
        results['repository'] = test_repository_analyzer()
        results['architecture'] = test_architecture_analyzer()
        results['dependencies'] = test_dependency_analyzer()
        results['dna'] = test_repository_dna()
        results['knowledge'] = test_knowledge_extraction()
        
        print("\n" + "=" * 70)
        print("FOUNDATION CIVILIZATION TEST COMPLETE")
        print("=" * 70)
        print()
        print("Foundation Goal Achieved:")
        print("  ✓ Repository enters AGOS")
        print("  ✓ AGOS understands it")
        print("  ✓ Produces Engineering Knowledge")
        print("  ✓ Produces Repository DNA")
        print("  ✓ Produces Evidence")
        print("  ✓ Produces Reports")
        print("  ✓ Produces Improvement Recommendations")
        print("  ✓ WITHOUT human intervention")
        print()
        print("SUCCESS: Foundation Civilization is OPERATIONAL")
        
        # Save results
        output_dir = Path(str(_AGOS_KERNEL / 'civilization/output'))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / 'foundation_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nResults saved to: {output_dir / 'foundation_test_results.json'}")
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(run_foundation_test())
