"""Kernel registries (``registry.capability``, ``registry.provider``) and their manifest.

R-Q-009: the registries live in memory; ``build_manifest`` turns a booted kernel's
registries into a versioned, deterministic snapshot. ``tools/audit/registry_manifest.py``
writes it to ``registry/manifest.json`` and ``tests/test_registry_manifest.py`` keeps
the committed file identical to what a fresh boot produces (it can never go stale).
"""
from typing import Any, Dict, List

MANIFEST_SCHEMA = 1
MANIFEST_FILE = "manifest.json"

__all__ = ["build_manifest", "MANIFEST_SCHEMA", "MANIFEST_FILE"]


def _entry(component: Any, kind: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "name": getattr(component, "name", type(component).__name__),
        "version": str(getattr(component, "version", None) or "1.0.0"),
        "class": f"{type(component).__module__}.{type(component).__qualname__}",
    }
    if kind == "capability":
        entry["skills"] = list(getattr(component, "skills", []) or [])
    return entry


def build_manifest(capability_registry: Any, provider_registry: Any, kernel_version: str) -> Dict[str, Any]:
    """Deterministic snapshot of the registries (sorted, no timestamps)."""
    capabilities: List[Dict[str, Any]] = sorted(
        (_entry(c, "capability") for c in capability_registry.list_all()), key=lambda e: e["name"])
    providers: List[Dict[str, Any]] = sorted(
        (_entry(p, "provider") for p in provider_registry.list_all()), key=lambda e: e["name"])
    for entry in providers:
        provider = provider_registry.get(entry["name"])
        entry["skills"] = sorted({s for c in capabilities for s in c["skills"]
                                  if provider is not None and provider.supports_skill(s)})
    return {
        "schema": MANIFEST_SCHEMA,
        "version": kernel_version,
        "generated_by": "tools/audit/registry_manifest.py",
        "capabilities": capabilities,
        "providers": providers,
    }
