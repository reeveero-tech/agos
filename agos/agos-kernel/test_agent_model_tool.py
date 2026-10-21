#!/usr/bin/env python3
"""Test script for Agent, Model, and Tool Packs."""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[1])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'
import sys
sys.path.insert(0, str(_AGOS_KERNEL))

from agent_packs.library import AgentPackLibrary, get_library as get_agent_library
from model_packs.library import ModelPackLibrary, get_library as get_model_library
from tool_packs.library import ToolPackLibrary, get_library as get_tool_library


def test_agent_packs():
    """Test agent packs."""
    print("=" * 60)
    print("Testing Agent Packs 1-50")
    print("=" * 60)
    
    library = get_agent_library()
    print(f"✓ Agent Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق AGENT-PACK-000001..000050 = 50
    assert len(library.packs) == 50, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({pack.metadata.provider})")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # Get agent
    openai = library.get("openai")
    if openai:
        print(f"\n✓ Agent: {openai.metadata.name}")
    # R-Q-001: وكيل openai موجود
    assert openai is not None, "openai agent pack missing"
    assert openai.metadata.provider, "openai agent pack has no provider"


def test_model_packs():
    """Test model packs."""
    print("\n" + "=" * 60)
    print("Testing Model Packs 1-50")
    print("=" * 60)
    
    library = get_model_library()
    print(f"✓ Model Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — الرصيد الفعلي 55 حزمة (الوثيقة تقول «1-50» — فرق موثق في سجل العمل)
    assert len(library.packs) == 55, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({pack.metadata.family})")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # List by family
    gpt_models = library.list_by_family("GPT")
    print(f"\n✓ GPT models: {len(gpt_models)}")
    claude_models = library.list_by_family("Claude")
    print(f"✓ Claude models: {len(claude_models)}")
    # R-Q-001: التصفية بالعائلة فعالة وكل نتيجتها من العائلة المطلوبة فعلاً
    assert len(gpt_models) == 5, len(gpt_models)
    assert len(claude_models) == 5, len(claude_models)
    assert all(x.metadata.family == "GPT" for x in gpt_models)
    assert all(x.metadata.family == "Claude" for x in claude_models)


def test_tool_packs():
    """Test tool packs."""
    print("\n" + "=" * 60)
    print("Testing Tool Packs 1-60")
    print("=" * 60)
    
    library = get_tool_library()
    print(f"✓ Tool Pack Library initialized")
    print(f"  Total packs: {len(library.packs)}")
    # R-Q-001: تأكيد فعلي — النطاق الموثق TOOL-PACK-000001..000060 = 60
    assert len(library.packs) == 60, len(library.packs)
    
    for i, (name, pack) in enumerate(list(library.packs.items())[:10]):
        print(f"  {i+1}. {pack.metadata.name} ({pack.metadata.category})")
        # المفتاح معرف والاسم معروض — الاسترجاع بالمفتاح يعيد الحزمة نفسها
        assert pack.metadata.name, (name, pack.metadata.name)
        assert library.get(name) is pack
    
    print(f"  ... and {len(library.packs) - 10} more")
    
    # List by category
    containers = library.list_by_category("container")
    print(f"\n✓ Container tools: {len(containers)}")
    testing = library.list_by_category("testing")
    print(f"✓ Testing tools: {len(testing)}")
    # R-Q-001: التصفية بالفئة فعالة وكل نتيجتها من الفئة المطلوبة فعلاً
    assert len(containers) == 4, len(containers)
    assert len(testing) == 5, len(testing)
    assert all(x.metadata.category == "container" for x in containers)
    assert all(x.metadata.category == "testing" for x in testing)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGOS AGENT, MODEL & TOOL PACKS")
    print("AGENT-PACK-000001 to AGENT-PACK-000050")
    print("MODEL-PACK-000001 to MODEL-PACK-000050")
    print("TOOL-PACK-000001 to TOOL-PACK-000060")
    print("=" * 60)
    
    test_agent_packs()
    test_model_packs()
    test_tool_packs()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()