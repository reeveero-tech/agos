"""Automatic Discovery System for Capabilities and Providers."""
import importlib
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from interfaces import ICapability, IProvider


def kernel_root() -> str:
    """Kernel root directory (the parent of this package) — R-W3-001.

    The loaders historically defaulted to ``os.path.dirname(__file__)`` — the
    ``discovery`` package itself — where no ``capabilities``/``providers`` exist, so a
    default boot always discovered nothing. The kernel root is the correct default.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_on_path(path: str) -> None:
    """Make ``path`` importable without shadowing earlier entries (ADR-0001)."""
    if path not in sys.path:
        sys.path.append(path)


def _is_concrete_subclass(attr: Any, base: type, module_name: str) -> bool:
    """A concrete implementation of ``base`` *defined in* ``module_name``."""
    import inspect
    return (isinstance(attr, type) and issubclass(attr, base) and attr is not base
            and getattr(attr, "__module__", "") == module_name
            and not inspect.isabstract(attr))


@dataclass
class Manifest:
    """Manifest for a discovered component."""
    id: str
    name: str
    version: str
    description: str
    path: str
    class_name: str
    skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    loaded_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    """Result of discovery process."""
    discovered: int = 0
    loaded: int = 0
    failed: int = 0
    manifests: List[Manifest] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class CapabilityManifest:
    """Manifest for a capability."""
    
    REQUIRED_FIELDS = ["id", "name", "version", "description"]
    
    @classmethod
    def from_class(cls, capability_class: Type, path: str) -> Manifest:
        """Create manifest from capability class."""
        instance = capability_class()
        
        return Manifest(
            id=getattr(instance, "id", capability_class.__name__),
            name=instance.name,
            version=getattr(instance, "version", "1.0.0"),
            description=instance.description,
            path=path,
            class_name=capability_class.__name__,
            skills=instance.skills if hasattr(instance, "skills") else [],
            metadata=getattr(instance, "metadata", {}),
        )
    
    @classmethod
    def validate(cls, manifest: Manifest) -> List[str]:
        """Validate manifest."""
        errors = []
        for field_name in cls.REQUIRED_FIELDS:
            if not getattr(manifest, field_name, None):
                errors.append(f"Missing required field: {field_name}")
        return errors


class ProviderManifest:
    """Manifest for a provider."""
    
    REQUIRED_FIELDS = ["name"]
    
    @classmethod
    def from_class(cls, provider_class: Type, path: str) -> Manifest:
        """Create manifest from provider class."""
        instance = provider_class()
        
        skills = []
        if hasattr(instance, "get_skills"):
            skills = instance.get_skills()
        elif hasattr(instance, "skills"):
            skills = instance.skills
        
        return Manifest(
            id=getattr(instance, "id", provider_class.__name__),
            name=instance.name,
            version=getattr(instance, "version", "1.0.0"),
            description=getattr(instance, "description", ""),
            path=path,
            class_name=provider_class.__name__,
            skills=skills,
            metadata=getattr(instance, "metadata", {}),
        )
    
    @classmethod
    def validate(cls, manifest: Manifest) -> List[str]:
        """Validate manifest."""
        errors = []
        if not manifest.name:
            errors.append("Missing required field: name")
        if not manifest.skills:
            errors.append("Provider must declare at least one skill")
        return errors


class CapabilityLoader:
    """Automatically discovers and loads capabilities."""
    
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = kernel_root()
        self.base_path = base_path
        self.capabilities_path = os.path.join(base_path, "capabilities")
    
    def discover(self) -> DiscoveryResult:
        """Discover all capabilities in the capabilities directory."""
        result = DiscoveryResult()
        
        if not os.path.isdir(self.capabilities_path):
            result.errors.append(f"Capabilities directory not found: {self.capabilities_path}")
            return result
        
        # R-W3-001: implementations defined in the package root (capabilities/__init__.py)
        for manifest in self._discover_root_capabilities():
            result.manifests.append(manifest)
            result.discovered += 1
            if manifest.errors:
                result.failed += 1
                result.errors.extend(manifest.errors)
            else:
                result.loaded += 1
        
        for item in sorted(os.listdir(self.capabilities_path)):
            item_path = os.path.join(self.capabilities_path, item)
            
            if item.startswith((".", "_")) or not os.path.isdir(item_path):
                continue
            
            manifest = self._discover_capability(item, item_path)
            result.manifests.append(manifest)
            result.discovered += 1
            
            if manifest.errors:
                result.failed += 1
                result.errors.extend(manifest.errors)
            else:
                result.loaded += 1
        
        return result
    
    def _discover_capability(self, name: str, path: str) -> Manifest:
        """Discover a single capability."""
        manifest = Manifest(
            id=name,
            name=name,
            version="1.0.0",
            description=f"Capability: {name}",
            path=path,
            class_name="",
        )
        
        try:
            module_name = f"capabilities.{name}"
            if module_name not in sys.modules:
                _ensure_on_path(self.base_path)
                importlib.import_module(module_name)
            
            module = sys.modules[module_name]
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, ICapability) and 
                    attr is not ICapability):
                    
                    manifest.class_name = attr_name
                    
                    try:
                        instance = attr()
                        manifest.name = instance.name
                        manifest.description = instance.description
                        manifest.skills = instance.skills
                    except Exception as e:
                        manifest.errors.append(f"Failed to instantiate: {e}")
                    
                    break
            
            if not manifest.class_name:
                manifest.errors.append(f"No ICapability implementation found in {name}")
            
        except Exception as e:
            manifest.errors.append(f"Failed to load: {e}")
        
        manifest.loaded_at = datetime.utcnow()
        return manifest
    
    def _discover_root_capabilities(self) -> List[Manifest]:
        """Discover every concrete ``ICapability`` defined in ``capabilities/__init__.py``.

        R-W3-001: the kernel's real capability (``RepositoryAnalysisCapability``) lives in
        the package root, which the sub-directory scan never looked at.
        """
        manifests: List[Manifest] = []
        try:
            _ensure_on_path(self.base_path)
            module = importlib.import_module("capabilities")
        except Exception as e:
            return [Manifest(id="capabilities", name="capabilities", version="1.0.0",
                             description="Capability package root", path=self.capabilities_path,
                             class_name="", errors=[f"Failed to load: {e}"],
                             loaded_at=datetime.utcnow())]
        for attr_name in sorted(dir(module)):
            attr = getattr(module, attr_name)
            if not _is_concrete_subclass(attr, ICapability, module.__name__):
                continue
            manifest = Manifest(id=attr_name, name=attr_name, version="1.0.0",
                                description=f"Capability: {attr_name}",
                                path=self.capabilities_path, class_name=attr_name,
                                metadata={"module": module.__name__})
            try:
                instance = attr()
                manifest.id = getattr(instance, "id", instance.name)
                manifest.name = instance.name
                manifest.version = getattr(instance, "version", "1.0.0")
                manifest.description = instance.description
                manifest.skills = list(instance.skills)
            except Exception as e:
                manifest.errors.append(f"Failed to instantiate: {e}")
            manifest.loaded_at = datetime.utcnow()
            manifests.append(manifest)
        return manifests
    
    def load_capability(self, manifest: Manifest) -> Optional[ICapability]:
        """Load a capability from manifest."""
        if manifest.errors:
            return None
        
        try:
            module_name = manifest.metadata.get("module") or f"capabilities.{os.path.basename(manifest.path)}"
            module = sys.modules.get(module_name)
            if not module:
                return None
            
            capability_class = getattr(module, manifest.class_name)
            return capability_class()
            
        except Exception as e:
            print(f"[LOADER] Failed to load capability {manifest.name}: {e}")
            return None


class ProviderLoader:
    """Automatically discovers and loads providers."""
    
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = kernel_root()
        self.base_path = base_path
        self.providers_path = os.path.join(base_path, "providers")
    
    def discover(self) -> DiscoveryResult:
        """Discover all providers."""
        result = DiscoveryResult()
        
        if not os.path.isdir(self.providers_path):
            result.errors.append(f"Providers directory not found: {self.providers_path}")
            return result
        
        # Look for provider implementations in __init__.py
        init_path = os.path.join(self.providers_path, "__init__.py")
        if os.path.isfile(init_path):
            # R-W3-001: every concrete IProvider, without reloading the module (a reload
            # re-creates the classes and breaks isinstance checks across the kernel).
            # ``_discover_provider_from_init`` (first class only) is kept for callers.
            for manifest in self._discover_providers_from_init(init_path):
                result.manifests.append(manifest)
                result.discovered += 1
                if manifest.errors:
                    result.failed += 1
                    result.errors.extend(manifest.errors)
                else:
                    result.loaded += 1
        
        return result
    
    def _discover_provider_from_init(self, path: str) -> Optional[Manifest]:
        """Discover provider from __init__.py."""
        parent_dir = os.path.dirname(path)
        provider_name = os.path.basename(parent_dir)
        
        manifest = Manifest(
            id=provider_name,
            name=provider_name,
            version="1.0.0",
            description=f"Provider: {provider_name}",
            path=parent_dir,
            class_name="",
        )
        
        try:
            module_name = "providers"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                _ensure_on_path(self.base_path)
                importlib.import_module(module_name)
            
            module = sys.modules[module_name]
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, IProvider) and 
                    attr is not IProvider):
                    
                    manifest.class_name = attr_name
                    
                    try:
                        instance = attr()
                        manifest.name = instance.name
                    except Exception as e:
                        manifest.errors.append(f"Failed to instantiate: {e}")
                    break
            
            if not manifest.class_name:
                manifest.errors.append(f"No IProvider implementation found in {provider_name}")
            
        except Exception as e:
            manifest.errors.append(f"Failed to load: {e}")
        
        manifest.loaded_at = datetime.utcnow()
        return manifest
    
    def _discover_providers_from_init(self, path: str) -> List[Manifest]:
        """All concrete ``IProvider`` implementations defined in ``providers/__init__.py``."""
        parent_dir = os.path.dirname(path)
        try:
            _ensure_on_path(self.base_path)
            module = importlib.import_module("providers")
        except Exception as e:
            return [Manifest(id="providers", name="providers", version="1.0.0",
                             description="Provider package root", path=parent_dir,
                             class_name="", errors=[f"Failed to load: {e}"],
                             loaded_at=datetime.utcnow())]
        manifests: List[Manifest] = []
        for attr_name in sorted(dir(module)):
            attr = getattr(module, attr_name)
            if not _is_concrete_subclass(attr, IProvider, module.__name__):
                continue
            manifest = Manifest(id=attr_name, name=attr_name, version="1.0.0",
                                description=f"Provider: {attr_name}", path=parent_dir,
                                class_name=attr_name, metadata={"module": module.__name__})
            try:
                instance = attr()
                manifest.name = instance.name
                manifest.version = getattr(instance, "version", "1.0.0")
            except Exception as e:
                manifest.errors.append(f"Failed to instantiate: {e}")
            manifest.loaded_at = datetime.utcnow()
            manifests.append(manifest)
        if not manifests:
            manifests.append(Manifest(id="providers", name="providers", version="1.0.0",
                                      description="Provider package root", path=parent_dir,
                                      class_name="", loaded_at=datetime.utcnow(),
                                      errors=["No IProvider implementation found in providers"]))
        return manifests
    
    def load_provider(self, manifest: Manifest) -> Optional[IProvider]:
        """Load a provider from manifest."""
        if manifest.errors:
            return None
        
        try:
            module_name = "providers"
            module = sys.modules.get(module_name)
            if not module:
                return None
            
            provider_class = getattr(module, manifest.class_name)
            return provider_class()
            
        except Exception as e:
            print(f"[LOADER] Failed to load provider {manifest.name}: {e}")
            return None


class AutoDiscovery:
    """Automatically discovers and registers all capabilities and providers."""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or kernel_root()
        self.capability_loader = CapabilityLoader(self.base_path)
        self.provider_loader = ProviderLoader(self.base_path)
    
    def discover_capabilities(self) -> DiscoveryResult:
        """Discover all capabilities."""
        return self.capability_loader.discover()
    
    def discover_providers(self) -> DiscoveryResult:
        """Discover all providers."""
        return self.provider_loader.discover()
    
    def load_capability(self, manifest: Manifest) -> Optional[ICapability]:
        """Load a capability."""
        return self.capability_loader.load_capability(manifest)
    
    def load_provider(self, manifest: Manifest) -> Optional[IProvider]:
        """Load a provider."""
        return self.provider_loader.load_provider(manifest)
