#!/usr/bin/env python3
"""Test script for Certification, Benchmark, and Audit Programs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from certification.library import CertificationLibrary, get_library as get_cert_library
from benchmark.library import BenchmarkLibrary, get_library as get_bench_library
from audit.library import AuditLibrary, get_library as get_audit_library


def test_certifications():
    """Test certifications."""
    print("=" * 60)
    print("Testing Certifications 1-30")
    print("=" * 60)
    
    library = get_cert_library()
    print(f"✓ Certification Library initialized")
    print(f"  Total certifications: {len(library.certifications)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق CERTIFICATION-000001..000030 = 30
    assert len(library.certifications) == 30, len(library.certifications)
    
    for i, (name, cert) in enumerate(list(library.certifications.items())[:10]):
        print(f"  {i+1}. {cert.metadata.name}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الشهادة نفسها
        assert cert.metadata.name, (name, cert.metadata.name)
        assert library.get(name) is cert
    
    print(f"  ... and {len(library.certifications) - 10} more")
    
    # Run certification
    result = library.certify("capability", {"name": "test"})
    print(f"\n✓ Certification result: {result.status.value}, score={result.score}")
    # R-Q-001: التأكيد الفعلي — النتيجة معلنة ومحققة لا مطبوعة فقط
    assert result.status.value == "passed", result.status.value
    assert result.score == 100.0, result.score


def test_benchmarks():
    """Test benchmarks."""
    print("\n" + "=" * 60)
    print("Testing Benchmarks 1-50")
    print("=" * 60)
    
    library = get_bench_library()
    print(f"✓ Benchmark Library initialized")
    print(f"  Total benchmarks: {len(library.benchmarks)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق BENCHMARK-000001..000050 = 50
    assert len(library.benchmarks) == 50, len(library.benchmarks)
    
    for i, (name, bench) in enumerate(list(library.benchmarks.items())[:10]):
        print(f"  {i+1}. {bench.name}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد القياس نفسه
        assert bench.name, (name, bench.name)
        assert library.get(name) is bench
    
    print(f"  ... and {len(library.benchmarks) - 10} more")
    
    # Run benchmark
    result = library.run("performance", {"name": "test"})
    print(f"\n✓ Benchmark result: score={result.score}")
    assert result.score == 100.0, result.score      # R-Q-001: تأكيد فعلي


def test_audits():
    """Test audits."""
    print("\n" + "=" * 60)
    print("Testing Audits 1-40")
    print("=" * 60)
    
    library = get_audit_library()
    print(f"✓ Audit Library initialized")
    print(f"  Total audits: {len(library.audits)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق AUDIT-000001..000040 = 40
    assert len(library.audits) == 40, len(library.audits)
    
    for i, (name, audit) in enumerate(list(library.audits.items())[:10]):
        print(f"  {i+1}. {audit.name}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد التدقيق نفسه
        assert audit.name, (name, audit.name)
        assert library.get(name) is audit
    
    print(f"  ... and {len(library.audits) - 10} more")
    
    # Run audit
    result = library.run("security", {"name": "test"})
    print(f"\n✓ Audit result: {result.status.value}, risk_score={result.risk_score}")
    assert result.status.value == "completed", result.status.value  # R-Q-001
    assert result.risk_score == 0.0, result.risk_score


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS CERTIFICATION, BENCHMARK & AUDIT PROGRAMS")
    print("CERTIFICATION-000001 to CERTIFICATION-000030")
    print("BENCHMARK-000001 to BENCHMARK-000050")
    print("AUDIT-000001 to AUDIT-000040")
    print("=" * 60)
    
    test_certifications()
    test_benchmarks()
    test_audits()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()