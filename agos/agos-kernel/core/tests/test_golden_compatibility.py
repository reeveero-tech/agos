"""
Golden Compatibility Tests
EXECUTION-KERNEL-FINALIZATION-000003

Tests that verify kernel compatibility with Python standards.
"""
# R-F-002 portable paths (see tools/migrate/portable_paths.py)
import os as _agos_os
from pathlib import Path as _AgosPath
_AGOS_ROOT = _AgosPath(_agos_os.environ.get('AGOS_ROOT') or _AgosPath(__file__).resolve().parents[3])
_AGOS_KERNEL = _AGOS_ROOT / 'agos-kernel'

import pytest
import sys
from pathlib import Path


class TestPythonCompatibility:
    """Golden tests for Python compatibility."""
    
    def test_python_version_compatible(self):
        """Kernel must be compatible with Python 3.8+."""
        assert sys.version_info >= (3, 8), \
            f"Kernel requires Python 3.8+, current: {sys.version_info}"
    
    def test_core_modules_python3_syntax(self):
        """Core modules must use valid Python 3 syntax."""
        kernel_dir = Path(str(_AGOS_KERNEL))
        
        syntax_errors = []
        for py_file in kernel_dir.rglob('*.py'):
            if '__pycache__' in str(py_file):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(py_file), 'exec')
            except SyntaxError as e:
                syntax_errors.append(f"{py_file}: {e}")
        
        assert len(syntax_errors) == 0, \
            f"Syntax errors found:\n" + "\n".join(syntax_errors)


class TestAPCompatibility:
    """Tests for API compatibility."""
    
    def test_kernel_has_version(self):
        """Kernel must expose version."""
        kernel_dir = Path(str(_AGOS_KERNEL))
        
        # Check for version in various places
        has_version = False
        
        # Check __init__.py
        init_file = kernel_dir / '__init__.py'
        if init_file.exists():
            with open(init_file, 'r') as f:
                content = f.read()
                if '__version__' in content or 'version' in content.lower():
                    has_version = True
        
        # Check main.py
        main_file = kernel_dir / 'main.py'
        if main_file.exists():
            with open(main_file, 'r') as f:
                content = f.read()
                if '__version__' in content or 'version' in content.lower():
                    has_version = True
        
        assert has_version, "Kernel should expose version information"


class TestDependencyCompatibility:
    """Tests for dependency compatibility."""
    
    def test_kernel_uses_only_standard_library_or_declared(self):
        """Kernel should use only standard library or declared dependencies."""
        # R-Q-009: the full stdlib (sys.stdlib_module_names), first-party names and the
        # dependencies declared in pyproject.toml; both ``import x`` and ``from x import``.
        # Imports guarded by ``try/except ImportError`` are optional. Stricter than before:
        # any undeclared third-party import fails (the old check tolerated up to 5).
        try:
            from .security_scan import allowed_import_roots, find_undeclared_imports, iter_sources
        except ImportError:
            from security_scan import allowed_import_roots, find_undeclared_imports, iter_sources
        kernel_dir = Path(str(_AGOS_KERNEL))
        allowed = allowed_import_roots(_AGOS_ROOT.parent)
        violations = [str(f) for path, tree in iter_sources(kernel_dir)
                      for f in find_undeclared_imports(path, tree, allowed)]
        
        if violations:
            pytest.fail(f"Undeclared third-party imports: {violations[:5]}")
