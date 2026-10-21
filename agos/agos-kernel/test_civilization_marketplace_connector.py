#!/usr/bin/env python3
"""Test script for Civilization, Marketplace, and Connector Programs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from civilization_packs.library import CivilizationPackLibrary, get_library as get_civ_library
from marketplace.library import Marketplace, get_marketplace
from connectors.library import ConnectorLibrary, get_library as get_conn_library


def test_civilization_packs():
    """Test civilization packs."""
    print("=" * 60)
    print("Testing Civilization Packs 1-30")
    print("=" * 60)
    
    library = get_civ_library()
    print(f"✓ Civilization Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق CIVILIZATION-PACK-000001..000030 = 30
    assert len(library.packs) == 30, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name}")
        print(f"      Domains: {', '.join(pack.metadata.domains[:3])}")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # Get pack
    foundation = library.get("foundation")
    if foundation:
        print(f"\n✓ Foundation pack: {foundation.metadata.description}")
    # R-Q-001: حزمة الأساس موجودة ولها نطاقات معلنة
    assert foundation is not None, "foundation pack missing"
    assert foundation.metadata.domains, "foundation pack has no domains"


def test_marketplace():
    """Test marketplace."""
    print("\n" + "=" * 60)
    print("Testing Marketplace 1-40")
    print("=" * 60)
    
    marketplace = get_marketplace()
    print(f"✓ Marketplace initialized")
    print(f"  Total categories: {len(marketplace.categories)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق MARKETPLACE-000001..000040 = 40
    assert len(marketplace.categories) == 40, len(marketplace.categories)
    
    print(f"  Categories: {', '.join(marketplace.categories[:15])}")
    print(f"  ... and {len(marketplace.categories) - 15} more")
    # R-Q-001: فئات معلنة فعلاً — الفئات الأولى الأساسية
    for expected in ("capability", "provider", "skill", "adapter", "workflow"):
        assert expected in marketplace.categories, expected
    
    # Publish an asset
    from marketplace.library import MarketplaceAsset
    asset = MarketplaceAsset("Test Capability", "capability", "AGOS")
    asset_id = marketplace.publish(asset)
    print(f"\n✓ Published asset: {asset_id}")
    # R-Q-001: النشر يُرجع معرفاً صالحاً لا مجرد طباعة
    assert isinstance(asset_id, str) and asset_id.startswith("asset-"), asset_id


def test_connectors():
    """Test connectors."""
    print("\n" + "=" * 60)
    print("Testing Connectors 1-50")
    print("=" * 60)
    
    library = get_conn_library()
    print(f"✓ Connector Library initialized")
    print(f"  Total connectors: {len(library.connectors)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق CONNECTOR-000001..000050 = 50
    assert len(library.connectors) == 50, len(library.connectors)
    
    for i, (name, conn) in enumerate(list(library.connectors.items())[:10]):
        print(f"  {i+1}. {conn.metadata.name} ({conn.metadata.provider})")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الموصِل نفسه
        assert conn.metadata.name, (name, conn.metadata.name)
        assert library.get(name) is conn
    
    print(f"  ... and {len(library.connectors) - 10} more")
    
    # Get connector
    github = library.get("github")
    if github:
        print(f"\n✓ GitHub connector: {github.metadata.description}")
    # R-Q-001: موصل github موجود وله موفر معلن
    assert github is not None, "github connector missing"
    assert github.metadata.provider, "github connector has no provider"


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS CIVILIZATION, MARKETPLACE & CONNECTOR PROGRAMS")
    print("CIVILIZATION-PACK-000001 to CIVILIZATION-PACK-000030")
    print("MARKETPLACE-000001 to MARKETPLACE-000040")
    print("CONNECTOR-000001 to CONNECTOR-000050")
    print("=" * 60)
    
    test_civilization_packs()
    test_marketplace()
    test_connectors()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()