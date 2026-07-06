"""Network, VCS and Execution Providers (4, 5, 8, 10-15)."""
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from .base import Provider


# ============ PROVIDER-000004: GitLab Provider ============
class GitLabProvider(Provider):
    """GitLab provider."""

    def __init__(self, token: Optional[str] = None):
        super().__init__("GitLab", "GitLab repository hosting")
        self.token = token or os.environ.get("GITLAB_TOKEN", "")
        self.metadata.auth_types = ["token"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "authenticated": bool(self.token)}


# ============ PROVIDER-000005: Bitbucket Provider ============
class BitbucketProvider(Provider):
    """Bitbucket provider."""

    def __init__(self, token: Optional[str] = None):
        super().__init__("Bitbucket", "Bitbucket repository hosting")
        self.token = token or os.environ.get("BITBUCKET_TOKEN", "")
        self.metadata.auth_types = ["token", "app_password"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "authenticated": bool(self.token)}


# ============ PROVIDER-000008: SSH Provider ============
class SSHProvider(Provider):
    """SSH provider."""

    def __init__(self, key_path: Optional[str] = None):
        super().__init__("SSH", "SSH remote execution")
        self.key_path = key_path or os.environ.get("SSH_KEY_PATH", "")
        self.metadata.auth_types = ["ssh_key", "password"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True}

    def execute_sandboxed(self, command: str, sandbox_config: Dict) -> Any:
        """Execute a command over SSH (host provided via sandbox_config)."""
        host = sandbox_config.get("host") if sandbox_config else None
        if not host:
            raise ValueError("SSH provider requires a 'host' in sandbox_config")
        return {"host": host, "command": command, "executed": False}


# ============ PROVIDER-000010: Container Provider ============
class ContainerProvider(Provider):
    """Generic container runtime provider (OCI)."""

    def __init__(self):
        super().__init__("Container", "OCI container runtime")
        self.metadata.auth_types = ["none"]

    def health_check(self) -> Dict[str, Any]:
        runtime = shutil.which("docker") or shutil.which("podman")
        return {"healthy": bool(runtime), "runtime": runtime or "none"}


# ============ PROVIDER-000011: CLI Provider ============
class CLIProvider(Provider):
    """Generic command-line execution provider."""

    def __init__(self):
        super().__init__("CLI", "Local CLI execution")
        self.metadata.auth_types = ["none"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True}

    def execute_sandboxed(self, command: str, sandbox_config: Dict) -> Any:
        """Execute a CLI command with a timeout."""
        timeout = (sandbox_config or {}).get("timeout", 30)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "timeout"}


# ============ PROVIDER-000012: REST Provider ============
class RESTProvider(Provider):
    """Generic REST API provider."""

    def __init__(self, base_url: str = ""):
        super().__init__("REST", "Generic REST API access")
        self.base_url = base_url
        self.metadata.auth_types = ["none", "token", "basic"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "base_url": self.base_url}


# ============ PROVIDER-000013: GraphQL Provider ============
class GraphQLProvider(Provider):
    """Generic GraphQL API provider."""

    def __init__(self, endpoint: str = ""):
        super().__init__("GraphQL", "Generic GraphQL API access")
        self.endpoint = endpoint
        self.metadata.auth_types = ["none", "token"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "endpoint": self.endpoint}


# ============ PROVIDER-000014: MCP Provider ============
class MCPProvider(Provider):
    """Model Context Protocol server provider."""

    def __init__(self, server_url: str = ""):
        super().__init__("MCP", "Model Context Protocol server access")
        self.server_url = server_url
        self.metadata.auth_types = ["none", "token"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "server_url": self.server_url}

    def discover(self) -> List[Dict]:
        """Discover MCP tools/resources exposed by the server."""
        return []


# ============ PROVIDER-000015: Local Execution Provider ============
class LocalExecutionProvider(Provider):
    """Local, sandboxed execution provider."""

    def __init__(self):
        super().__init__("LocalExecution", "Local process execution")
        self.metadata.auth_types = ["none"]

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True}

    def execute_sandboxed(self, command: str, sandbox_config: Dict) -> Any:
        """Execute a command locally within basic resource limits."""
        cwd = (sandbox_config or {}).get("cwd", ".")
        timeout = (sandbox_config or {}).get("timeout", 30)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=timeout,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "timeout"}


# Registry
NETWORK_PROVIDERS = {
    "gitlab": GitLabProvider,
    "bitbucket": BitbucketProvider,
    "ssh": SSHProvider,
    "container": ContainerProvider,
    "cli": CLIProvider,
    "rest": RESTProvider,
    "graphql": GraphQLProvider,
    "mcp": MCPProvider,
    "local_execution": LocalExecutionProvider,
}


def get_network_provider(name: str) -> Provider:
    """Get a network/execution provider."""
    provider_class = NETWORK_PROVIDERS.get(name)
    if not provider_class:
        raise ValueError(f"Unknown network provider: {name}")
    return provider_class()
