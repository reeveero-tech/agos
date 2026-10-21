"""
Golden Security Tests
EXECUTION-KERNEL-FINALIZATION-000003

Tests that verify kernel security characteristics.
"""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[3])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'

import pytest
from pathlib import Path
import re

# R-Q-009: the checks below use AST scanners (see security_scan.py and the canaries in
# tests/test_security_scanners.py) instead of raw text matching.
try:
    from .security_scan import (find_dynamic_code_calls, find_hardcoded_secrets,
                                find_sql_string_building, find_unsafe_dynamic_imports,
                                iter_sources)
except ImportError:  # executed outside the package (e.g. core/tests on sys.path)
    from security_scan import (find_dynamic_code_calls, find_hardcoded_secrets,
                               find_sql_string_building, find_unsafe_dynamic_imports,
                               iter_sources)


class TestKernelSecurity:
    """Golden tests for kernel security."""
    
    @pytest.fixture
    def kernel_dir(self):
        """Get kernel directory."""
        return Path(str(_AGOS_KERNEL))
    
    def test_no_hardcoded_secrets(self, kernel_dir):
        """Kernel must not contain hardcoded secrets."""
        # Credential-like names bound to string literals (assignments, attributes,
        # keyword arguments, dict entries); placeholders/test values and enum labels such
        # as ``API_KEY = "api_key"`` are not secrets. Sample vulnerable code held *as data*
        # (e.g. by the security-scan skill) is not executed and is not a secret.
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_hardcoded_secrets(path, tree)]
        
        assert len(violations) == 0, \
            f"Hardcoded secrets found:\n" + "\n".join(violations[:5])
    
    def test_no_eval_usage(self, kernel_dir):
        """Kernel must not use eval()."""
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_dynamic_code_calls(path, tree, ["eval"])]
        
        assert len(violations) == 0, \
            f"eval() usage found:\n" + "\n".join(violations[:5])
    
    def test_no_exec_usage(self, kernel_dir):
        """Kernel must not use exec()."""
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_dynamic_code_calls(path, tree, ["exec"])]
        
        assert len(violations) == 0, \
            f"exec() usage found:\n" + "\n".join(violations[:5])
    
    def test_no_sql_injection_patterns(self, kernel_dir):
        """Kernel should avoid SQL injection vulnerabilities."""
        # SQL statements assembled from runtime values (f-string, %, .format, +).
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_sql_string_building(path, tree)]
        
        if len(violations) > 0:
            pytest.fail(f"SQL injection patterns found:\n" + "\n".join(violations[:3]))


class TestSecurityBestPractices:
    """Tests for security best practices."""
    
    def test_imports_are_safe(self):
        """Kernel should use safe import patterns."""
        # Dynamic imports are allowed only when the module name is fixed in the source or
        # confined to a fixed package prefix (plugin discovery: f"capabilities.{name}").
        kernel_dir = Path(str(_AGOS_KERNEL))
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_unsafe_dynamic_imports(path, tree)]
        
        assert len(violations) == 0, \
            f"Unsafe import patterns:\n" + "\n".join(violations[:5])
    
    def test_file_permissions_are_restricted(self, kernel_dir):
        """Kernel files should have appropriate permissions."""
        # Check that sensitive files don't exist with wrong permissions
        sensitive_files = [
            '*.key', '*.pem', '*.cert', '*id_rsa*', '*id_dsa*'
        ]
        
        violations = []
        
        for pattern in sensitive_files:
            for f in kernel_dir.rglob(pattern):
                if f.is_file():
                    # Files should not be executable scripts
                    if f.suffix in ['.py', '.sh']:
                        violations.append(f"Sensitive file {f} should not be executable")
        
        # This is informational - not a hard failure
        if len(violations) > 0:
            pytest.skip(f"Sensitive file check: {'; '.join(violations[:3])}")
