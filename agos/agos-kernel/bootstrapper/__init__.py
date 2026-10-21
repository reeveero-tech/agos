"""Runtime Bootstrapper - Initializes the entire AGOS Kernel."""
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from container import Container, Lifetime, LifetimeManager
from contract_engine import ContractEngine, ContractType
from discovery import AutoDiscovery, kernel_root
from event_engine import EventEngine
from events import EventBus
from mission_engine import MissionEngine
from pipeline import ExecutionPipeline
from resolvers import CapabilityResolver, ProviderResolver
from registry.capability import CapabilityRegistry
from registry.provider import ProviderRegistry


@dataclass
class BootstrapResult:
    """Result of bootstrap operation."""
    success: bool
    kernel_version: str = "0.2.0"
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    loaded_capabilities: List[str] = field(default_factory=list)
    loaded_providers: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class Bootstrapper:
    """
    Runtime Bootstrapper.
    
    Boot Order:
    1. Load Configuration
    2. Build Container
    3. Register Infrastructure
    4. Load Capabilities
    5. Load Providers
    6. Validate Contracts
    7. Initialize Event Engine
    8. Initialize Mission Engine
    9. Kernel Ready
    """
    
    KERNEL_VERSION = "0.2.0"
    
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            # R-W3-001: the kernel root, where capabilities/ and providers/ live. The old
            # default (this package's own directory) made every default boot fail with
            # "No capabilities loaded".
            base_path = kernel_root()
        self.base_path = base_path
        
        self.container: Optional[Container] = None
        self.event_engine: Optional[EventEngine] = None
        self.event_bus: Optional[EventBus] = None
        self.contract_engine: Optional[ContractEngine] = None
        self.mission_engine: Optional[MissionEngine] = None
        self.result: Optional[BootstrapResult] = None
    
    def bootstrap(self) -> BootstrapResult:
        """Bootstrap the kernel."""
        self.result = BootstrapResult(success=False, kernel_version=self.KERNEL_VERSION, started_at=datetime.utcnow())
        
        try:
            print("=" * 60)
            print(f"AGOS KERNEL v{self.KERNEL_VERSION} BOOTSTRAP")
            print("=" * 60)
            
            # Step 1-3: Container
            print("\n[1-3] Building container...")
            self._build_container()
            print("✓ Container built")
            
            # Step 4: Load Capabilities
            print("\n[4] Loading capabilities...")
            self._load_capabilities()
            print(f"✓ {len(self.result.loaded_capabilities)} capabilities loaded")
            
            # Step 5: Load Providers
            print("\n[5] Loading providers...")
            self._load_providers()
            print(f"✓ {len(self.result.loaded_providers)} providers loaded")
            
            # Step 6: Validate Contracts
            print("\n[6] Validating contracts...")
            if not self._validate_contracts():
                raise Exception("Contract validation failed")
            print("✓ Contracts validated")
            
            # Step 7: Initialize Event Engine
            print("\n[7] Initializing event engine...")
            self._initialize_event_engine()
            print("✓ Event engine initialized")
            
            # Step 8: Initialize Mission Engine
            print("\n[8] Initializing mission engine...")
            self._initialize_mission_engine()
            print("✓ Mission engine initialized")
            
            # Step 9: Complete
            self.result.success = True
            self.result.completed_at = datetime.utcnow()
            self.result.duration_ms = int((self.result.completed_at - self.result.started_at).total_seconds() * 1000)
            
            print("\n" + "=" * 60)
            print("✅ AGOS KERNEL READY")
            print("=" * 60)
            print(f"\nVersion: {self.KERNEL_VERSION}")
            print(f"Capabilities: {len(self.result.loaded_capabilities)}")
            print(f"Providers: {len(self.result.loaded_providers)}")
            print(f"Startup time: {self.result.duration_ms}ms")
            
            return self.result
            
        except Exception as e:
            self.result.success = False
            self.result.errors.append(str(e))
            self.result.completed_at = datetime.utcnow()
            self.result.duration_ms = int((self.result.completed_at - self.result.started_at).total_seconds() * 1000)
            print(f"\n❌ BOOTSTRAP FAILED: {e}")
            return self.result
    
    def _build_container(self) -> None:
        """Build dependency injection container."""
        self.container = Container()
        self._capability_registry = CapabilityRegistry()
        self._provider_registry = ProviderRegistry()
    
    def _load_capabilities(self) -> None:
        """Load capabilities via discovery."""
        self._discovery = AutoDiscovery(self.base_path)
        result = self._discovery.discover_capabilities()
        
        for manifest in result.manifests:
            if manifest.errors:
                # Not fatal: e.g. catalogue sub-packages that hold no ICapability yet
                # (wired by R-W3-002). Recorded so nothing is silently ignored.
                self.result.warnings.extend(f"capability {manifest.id}: {e}" for e in manifest.errors)
            if not manifest.errors:
                capability = self._discovery.load_capability(manifest)
                if capability:
                    self._capability_registry.register(capability)
                    self.result.loaded_capabilities.append(capability.name)
    
    def _load_providers(self) -> None:
        """Load providers via discovery."""
        result = self._discovery.discover_providers()
        
        for manifest in result.manifests:
            if manifest.errors:
                self.result.warnings.extend(f"provider {manifest.id}: {e}" for e in manifest.errors)
            if not manifest.errors:
                provider = self._discovery.load_provider(manifest)
                if provider:
                    self._provider_registry.register(provider)
                    self.result.loaded_providers.append(provider.name)
    
    def _validate_contracts(self) -> bool:
        """Validate all contracts."""
        if len(self.result.loaded_capabilities) == 0:
            self.result.errors.append("No capabilities loaded")
            return False
        if len(self.result.loaded_providers) == 0:
            self.result.errors.append("No providers loaded")
            return False
        # R-W3-001: every loaded component passes the contract engine (step 6).
        self.contract_engine = ContractEngine()
        valid = True
        checks = [(ContractType.CAPABILITY, c) for c in self._capability_registry.list_all()]
        checks += [(ContractType.PROVIDER, p) for p in self._provider_registry.list_all()]
        for contract_type, component in checks:
            verdict = self.contract_engine.validate(contract_type, component)
            self.contract_engine.registry.register(verdict)
            if not verdict.is_valid:
                valid = False
                self.result.errors.extend(
                    f"{contract_type.value} {verdict.contract_id}: {e.message}" for e in verdict.errors)
        return valid
    
    def _initialize_event_engine(self) -> None:
        """Initialize event engine."""
        self.event_engine = EventEngine()
        # R-W3-001: the pipeline publishes on an EventBus; it was given ``None``, so
        # the first mission crashed on ``None.publish``.
        self.event_bus = EventBus()
    
    def _initialize_mission_engine(self) -> None:
        """Initialize mission engine."""
        capability_resolver = CapabilityResolver(self._capability_registry)
        provider_resolver = ProviderResolver(self._provider_registry, self._capability_registry)
        
        pipeline = ExecutionPipeline(
            event_bus=self.event_bus,
            capability_resolver=capability_resolver,
            provider_resolver=provider_resolver
        )
        
        self.mission_engine = MissionEngine(pipeline)
    
    def get_kernel(self):
        """Get the initialized kernel."""
        return {
            "container": self.container,
            "event_engine": self.event_engine,
            "event_bus": self.event_bus,
            "contract_engine": self.contract_engine,
            "mission_engine": self.mission_engine,
            "capability_registry": self._capability_registry,
            "provider_registry": self._provider_registry,
        }
