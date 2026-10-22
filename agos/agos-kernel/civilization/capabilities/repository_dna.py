"""
Repository DNA Generator
PHASE-02: Foundation Civilization

Generates unique DNA fingerprints for repositories.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DNAFragment:
    """A fragment of repository DNA."""
    type: str  # structure, code, config, dependency
    hash: str
    value: Any


class RepositoryDNA:
    """
    Repository DNA Generator.
    
    Generates unique DNA fingerprints for software repositories.
    DNA can be used to identify, compare, and track repositories.
    """
    
    VERSION = "1.0"
    
    def generate(self, repo_path: str) -> Dict[str, Any]:
        """Generate Repository DNA.

        R-W2-006 (ADR-0005): تفويض المسح إلى الخدمة المشتركة — الخط الواحد؛
        البصمة تُحسب من فهرس الخدمة ومحتواها المقروء (لا مسح قرص ثانٍ). توثيق
        توحيد سلوكي: المجلدات المستثناة (node_modules وأمثالها) لم تعد تدخل
        في بصمة الشيفرة (الاسم وحده لم يكن يستثنيها قبلًا)، والملفات غير
        الصالحة UTF-8 لم تعد تُهمل صامتة.
        """
        from agos_kernel.capabilities.analysis_service import (
            ScanPolicy, get_analysis_service)

        root = Path(repo_path).resolve()
        # سياسة الهاش: ملفات البصمة (py/config/dep) تُهشّ أثناء المسح نفسه —
        # قراءة utf-8 صارمة كما في القديم (فاقد الترميز يُتخطى لا يُهش بديلاً)،
        # فلا يفقد الملف الكبير أو المتغير وظيفة البصمة.
        shared = get_analysis_service().analyze_path(
            repo_path,
            policy=ScanPolicy(exclude=self._excluded,
                               hash_predicate=self._hash_predicate))

        fragments = {
            'structure': self._structure_dna_from_index(shared.files),
            'code': self._code_dna_from_index(shared),
            'config': self._config_dna_from_index(shared),
            'dependency': self._dependency_dna_from_index(shared),
        }

        # Combine all fragments
        combined = self._combine_fragments(fragments)

        return {
            'version': self.VERSION,
            'repository': root.name,
            'path': str(root),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'fragments': fragments,
            'dna': combined,
            'signature': hashlib.sha256(combined.encode()).hexdigest()[:32],
        }

    #: أسماء الاستثناء القديمة بالضبط (G2 — سلوك _should_exclude نفسه)
    _excluded_names = frozenset({
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', 'venv', '.venv',
        'env', 'dist', 'build', '.egg-info', '.pytest_cache', '.mypy_cache',
        '.tox', '.coverage', '.DS_Store', 'Thumbs.db',
    })

    @classmethod
    def _excluded(cls, name: str) -> bool:
        """سلوك _should_exclude القديم بالضبط: الأسماء + امتدادات pyc/pyo."""
        return name in cls._excluded_names or name.endswith(('.pyc', '.pyo'))

    #: ملفات البصمة — هاش أثناء المسح (نفس ملفات القديم: py + config + dep)
    _hash_names = frozenset({
        'package.json', 'setup.py', 'pyproject.toml', 'requirements.txt',
        'Dockerfile', 'docker-compose.yml', '.gitignore', '.dockerignore',
        'tsconfig.json', 'jest.config.js', 'pytest.ini', 'tox.ini',
        'package-lock.json', 'Pipfile', 'Pipfile.lock', 'go.mod', 'Cargo.toml',
    })

    @classmethod
    def _hash_predicate(cls, name: str) -> bool:
        return name.endswith('.py') or name in cls._hash_names

    def _structure_dna_from_index(self, files) -> str:
        """بصمة البنية من الفهرس — نفس دلالات _generate_structure_dna القديمة."""
        elements = []
        for entry in sorted(files, key=lambda e: e.path):
            rel_path = entry.path
            if entry.is_dir:
                elements.append(f"DIR:{rel_path}")
            else:
                elements.append(f"FILE:{rel_path}")
        structure_str = "\n".join(elements)
        return hashlib.sha256(structure_str.encode()).hexdigest()[:16]

    def _code_dna_from_index(self, shared) -> str:
        """بصمة الشيفرة من هاش المسح — دلالات القديمة نفسها (py مُهشّة
        أثناء المسح بقراءة صارمة؛ فاقد الترميز يُتخطى كما كان)."""
        code_hashes = []
        for entry in shared.files:
            if entry.is_dir or not entry.path.endswith('.py'):
                continue
            if entry.sha256:
                code_hashes.append(entry.sha256)
        combined = "".join(sorted(code_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _config_dna_from_index(self, shared) -> str:
        """بصمة الإعدادات من محتوى الخدمة المقروء — دلالات القديمة نفسها."""
        config_names = {
            'package.json', 'setup.py', 'pyproject.toml', 'requirements.txt',
            'Dockerfile', 'docker-compose.yml', '.gitignore', '.dockerignore',
            'tsconfig.json', 'jest.config.js', 'pytest.ini', 'tox.ini',
        }
        config_hashes = []
        for entry in shared.files:
            if entry.is_dir or Path(entry.path).name not in config_names:
                continue
            if entry.sha256:
                config_hashes.append(entry.sha256)
        if not config_hashes:
            return "NO_CONFIG"
        combined = "".join(sorted(config_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _dependency_dna_from_index(self, shared) -> str:
        """بصمة الاعتماديات من محتوى الخدمة المقروء — دلالات القديمة نفسها."""
        dep_names = {
            'requirements.txt', 'package.json', 'package-lock.json',
            'Pipfile', 'Pipfile.lock', 'go.mod', 'Cargo.toml',
        }
        dep_hashes = []
        for entry in shared.files:
            if entry.is_dir or Path(entry.path).name not in dep_names:
                continue
            if entry.sha256:
                dep_hashes.append(entry.sha256)
        if not dep_hashes:
            return "NO_DEPS"
        combined = "".join(sorted(dep_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _generate_structure_dna(self, repo_path: Path) -> str:
        """Generate DNA from repository structure."""
        structure_elements = []
        
        for item in sorted(repo_path.rglob('*')):
            if self._should_exclude(item):
                continue
            
            rel_path = str(item.relative_to(repo_path))
            
            if item.is_dir():
                structure_elements.append(f"DIR:{rel_path}")
            else:
                structure_elements.append(f"FILE:{rel_path}")
        
        structure_str = "\n".join(structure_elements)
        return hashlib.sha256(structure_str.encode()).hexdigest()[:16]
    
    def _generate_code_dna(self, repo_path: Path) -> str:
        """Generate DNA from code content."""
        code_hashes = []
        
        for py_file in repo_path.rglob('*.py'):
            if self._should_exclude(py_file):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Hash function/class names
                code_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
                code_hashes.append(code_hash)
            except Exception:
                pass
        
        combined = "".join(sorted(code_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _generate_config_dna(self, repo_path: Path) -> str:
        """Generate DNA from configuration files."""
        config_files = [
            'package.json', 'setup.py', 'pyproject.toml', 'requirements.txt',
            'Dockerfile', 'docker-compose.yml', '.gitignore', '.dockerignore',
            'tsconfig.json', 'jest.config.js', 'pytest.ini', 'tox.ini',
        ]
        
        config_hashes = []
        
        for config_file in config_files:
            for file_path in repo_path.rglob(config_file):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    config_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
                    config_hashes.append(config_hash)
                except Exception:
                    pass
        
        if not config_hashes:
            return "NO_CONFIG"
        
        combined = "".join(sorted(config_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _generate_dependency_dna(self, repo_path: Path) -> str:
        """Generate DNA from dependencies."""
        dep_hashes = []
        
        dep_files = [
            'requirements.txt', 'package.json', 'package-lock.json',
            'Pipfile', 'Pipfile.lock', 'go.mod', 'Cargo.toml',
        ]
        
        for dep_file in dep_files:
            for file_path in repo_path.rglob(dep_file):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    dep_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
                    dep_hashes.append(dep_hash)
                except Exception:
                    pass
        
        if not dep_hashes:
            return "NO_DEPS"
        
        combined = "".join(sorted(dep_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _combine_fragments(self, fragments: Dict[str, str]) -> str:
        """Combine all fragments into single DNA."""
        combined = "|".join([
            f"{k}:{v}" for k, v in sorted(fragments.items())
        ])
        return combined
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded."""
        excluded = [
            '__pycache__', '.git', '.svn', '.hg',
            'node_modules', 'venv', '.venv', 'env',
            'dist', 'build', '.egg-info',
            '*.pyc', '*.pyo', '.pytest_cache',
            '.mypy_cache', '.tox', '.coverage',
            '.DS_Store', 'Thumbs.db',
        ]
        
        name = path.name
        for ex in excluded:
            if ex.startswith('*'):
                if name.endswith(ex[1:]):
                    return True
            elif name == ex:
                return True
        
        return False
    
    def compare(self, dna1: Dict, dna2: Dict) -> Dict[str, Any]:
        """Compare two repository DNAs."""
        similarity = 0
        differences = []
        
        for fragment in ['structure', 'code', 'config', 'dependency']:
            if dna1['fragments'].get(fragment) == dna2['fragments'].get(fragment):
                similarity += 25
            else:
                differences.append(fragment)
        
        return {
            'similarity_percent': similarity,
            'differences': differences,
            'same_repository': similarity == 100,
        }
