"""
Repository Analysis Capability
PHASE-02: Foundation Civilization

Analyzes software repositories to understand their structure and content.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RepositoryInfo:
    """Repository information."""
    name: str = ""
    path: str = ""
    size_bytes: int = 0
    file_count: int = 0
    directory_count: int = 0
    language: str = ""
    languages: Dict[str, int] = field(default_factory=dict)
    files: List[Dict] = field(default_factory=list)
    # R-W2-003: per-language line counts — the weight behind ``language``.
    # Appended last so positional construction is unchanged.
    language_lines: Dict[str, int] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    
    
class RepositoryAnalyzer:
    """
    Repository Analyzer.
    
    Analyzes software repositories and produces comprehensive information.
    """
    
    def __init__(self):
        self.excluded_patterns = [
            '__pycache__', '.git', '.svn', '.hg',
            'node_modules', 'venv', '.venv', 'env',
            'dist', 'build', '.egg-info', '__pycache__',
            '*.pyc', '*.pyo', '.pytest_cache', '.tox',
            '.coverage', 'htmlcov', '.mypy_cache',
            '.DS_Store', 'Thumbs.db', '.idea', '.vscode'
        ]
        
        self.language_extensions = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.hpp': 'C++ Header',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.less': 'Less',
            '.json': 'JSON',
            '.xml': 'XML',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.md': 'Markdown',
            '.txt': 'Text',
            '.sql': 'SQL',
            '.sh': 'Shell',
            '.bash': 'Bash',
            '.zsh': 'Zsh',
            '.ps1': 'PowerShell',
            '.dockerfile': 'Dockerfile',
            '.toml': 'TOML',
            '.cfg': 'Config',
            '.ini': 'INI',
            '.conf': 'Config',
        }
    
    def analyze(self, repo_path: str) -> Dict[str, Any]:
        """
        Analyze a repository.

        Returns comprehensive repository information.

        R-W2-006 (ADR-0005): التفويض إلى الخدمة المشتركة — الخط الواحد. المسح
        والفهرس وإحصاء الأسطر مرة واحدة في الخدمة؛ هذا الإسقاط يحافظ على
        التصنيف القديم بالضبط (خريطة الامتدادات هنا تجعل JSON/YAML/Markdown
        لغاتٍ — إسقاط صريح لا يُسقط صمتاً، ومقياس مختلف عن لغات ملفات الشيفرة
        في DNA النواة). المجلدات المستثناة لم تعد تنفّط الحجم (توثيق في
        ADR-0005 — توحيد سلوكي).
        """
        from agos_kernel.capabilities.analysis_service import (
            CIV_SCAN_POLICY, get_analysis_service)

        root = Path(repo_path).resolve()
        shared = get_analysis_service().analyze_path(repo_path, policy=CIV_SCAN_POLICY)

        info = RepositoryInfo(name=root.name, path=str(root))
        for entry in shared.files:
            if entry.is_dir:
                info.directory_count += 1
                continue
            info.file_count += 1
            # التصنيف القديم: الامتداد مصغّراً (suffix.lower()) والامتدادات
            # المعروفة لغات والبقية Unknown — إسقاط صريح لا يُسقط صمتاً.
            # وأسطر اللغات من **أسطر المحتوى المقروء** (دلالة القراءة القديمة
            # للحضارة: replace) — لا مقاييس التصنيف
            ext = entry.extension.lower()
            lang = self.language_extensions.get(ext)
            if entry.lines >= 0 and lang is not None:
                info.language_lines[lang] = info.language_lines.get(lang, 0) + entry.lines
            if lang is not None:
                info.languages[lang] = info.languages.get(lang, 0) + 1
            info.files.append({
                'path': entry.path,
                'name': Path(entry.path).name,
                'extension': entry.extension,
                'size': entry.size_bytes,
                'language': self.language_extensions.get(ext, 'Unknown'),
            })

        # Detect primary language — by lines first, then file count (R-W2-003)
        info.language = self._detect_primary_language(info.languages, info.language_lines)

        # Generate structure — إسقاط الشكل القديم من الفهرس (لا مسح ثانٍ)
        info.structure = self._structure_from_index(shared.files, root.name)

        # Calculate size — مجموع أحجام ملفات الفهرس (المستثنى لا ينفّط الحجم)
        info.size_bytes = sum(f.size_bytes for f in shared.files if not f.is_dir)

        return self._to_dict(info)

    def _structure_from_index(self, files, root_name: str) -> Dict:
        """شجرة البنية بالشكل القديم من فهرس الخدمة — لا مسح ثانٍ للقرص.

        نفس دلالات ``_generate_structure`` القديمة: الجذر باسم المستودع،
        مجلدات متفرعة، ملفات أوراق، و``{'truncated': True}`` عند العمق 3،
        والأبناء مرتبون بالاسم.
        """
        # بناء شجرة المسارات من الفهرس
        tree: Dict = {'children': {}}
        for entry in files:
            parts = Path(entry.path).parts
            node = tree
            for part in parts[:-1]:
                node = node['children'].setdefault(part, {'children': {}})
            node['children'].setdefault(parts[-1],
                                        {'entry': entry, 'children': {}})

        def build(name: str, node: Dict, depth: int) -> Dict:
            if depth >= 3:
                return {'truncated': True}
            children = []
            for child_name in sorted(node['children']):
                child = node['children'][child_name]
                entry = child.get('entry')
                if entry is not None and not entry.is_dir:
                    children.append({
                        'name': child_name,
                        'type': 'file',
                        'extension': entry.extension,
                    })
                else:
                    children.append(build(child_name, child, depth + 1))
            return {'name': name, 'type': 'directory', 'children': children}

        return build(root_name, tree, 0)
    
    def _scan_directory(self, path: Path, info: RepositoryInfo) -> None:
        """Scan directory and collect file information."""
        try:
            for item in path.iterdir():
                # Skip excluded patterns
                if self._should_exclude(item):
                    continue
                
                if item.is_dir():
                    info.directory_count += 1
                    self._scan_directory(item, info)
                elif item.is_file():
                    info.file_count += 1
                    
                    # Track language
                    ext = item.suffix.lower()
                    if ext in self.language_extensions:
                        lang = self.language_extensions[ext]
                        info.languages[lang] = info.languages.get(lang, 0) + 1
                        # R-W2-003: weight by lines — read only small text files, and
                        # never let a failed read break the scan.
                        try:
                            if item.stat().st_size <= 1_000_000:
                                with open(item, 'r', encoding='utf-8', errors='replace') as fh:
                                    text = fh.read()
                                if "\x00" not in text:
                                    lines = text.count("\n") + (0 if text.endswith("\n") else 1) if text else 0
                                    info.language_lines[lang] = info.language_lines.get(lang, 0) + lines
                        except (OSError, ValueError):
                            pass
                    
                    # Record file info
                    try:
                        file_size = item.stat().st_size
                        info.files.append({
                            'path': str(item.relative_to(path)),
                            'name': item.name,
                            'extension': item.suffix,
                            'size': file_size,
                            'language': self.language_extensions.get(item.suffix.lower(), 'Unknown'),
                        })
                    except Exception:
                        pass
        except PermissionError:
            pass
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded."""
        name = path.name
        for pattern in self.excluded_patterns:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False
    
    def _detect_primary_language(self, languages: Dict[str, int], language_lines: Optional[Dict[str, int]] = None) -> str:
        """Detect primary language: most lines first, then most files (R-W2-003).
        
        Lines are the weight (a thousand-line module outweighs ten one-line scripts);
        file count is the tie-break, then the name alphabetically — deterministic.
        """
        if not languages:
            return "Unknown"
        lines = language_lines or {}
        if lines:
            best = max(set(languages) | set(lines),
                       key=lambda lang: (lines.get(lang, 0), languages.get(lang, 0), tuple(-ord(c) for c in lang)))
            return best
        return max(languages.items(), key=lambda x: x[1])[0]
    
    def _generate_structure(self, path: Path, max_depth: int = 3, current_depth: int = 0) -> Dict:
        """Generate repository structure."""
        if current_depth >= max_depth:
            return {'truncated': True}
        
        structure = {'name': path.name, 'type': 'directory', 'children': []}
        
        try:
            for item in sorted(path.iterdir()):
                if self._should_exclude(item):
                    continue
                    
                if item.is_dir():
                    structure['children'].append(
                        self._generate_structure(item, max_depth, current_depth + 1)
                    )
                else:
                    structure['children'].append({
                        'name': item.name,
                        'type': 'file',
                        'extension': item.suffix,
                    })
        except PermissionError:
            pass
        
        return structure
    
    def _calculate_size(self, path: Path) -> int:
        """Calculate total repository size."""
        total = 0
        try:
            for item in path.rglob('*'):
                if item.is_file() and not self._should_exclude(item):
                    try:
                        total += item.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return total
    
    def _to_dict(self, info: RepositoryInfo) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': info.name,
            'path': info.path,
            'size_bytes': info.size_bytes,
            'size_mb': round(info.size_bytes / (1024 * 1024), 2),
            'file_count': info.file_count,
            'directory_count': info.directory_count,
            'primary_language': info.language,
            'languages': info.languages,
            'structure': info.structure,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
