"""Repository Analysis Capability."""
import copy
import os
import subprocess
from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from contracts import RepositoryDNA, RepositorySnapshot
from interfaces import ICapability


class RepositoryAnalysisInput:
    """Input for Repository Analysis."""
    def __init__(self, url: str, branch: str = "main"):
        self.url = url
        self.branch = branch


class RepositoryAnalysisCapability(ICapability):
    """
    Analyzes a repository and generates its DNA.
    
    Pipeline:
    1. CloneRepository
    2. ReadRepository
    3. DetectLanguages
    4. DetectFrameworks
    5. GenerateDNA
    """
    
    @property
    def name(self) -> str:
        return "RepositoryAnalysis"
    
    @property
    def description(self) -> str:
        return "Analyzes repositories and generates DNA"
    
    @property
    def skills(self) -> List[str]:
        return ["CloneRepository", "ReadRepository", "GenerateDNA"]
    
    def execute(self, input_data: Any) -> RepositoryDNA:
        """Execute the capability."""
        if isinstance(input_data, dict):
            url = input_data.get("url", "")
            branch = input_data.get("branch", "main")
        elif hasattr(input_data, "url"):
            url = input_data.url
            branch = input_data.branch
        else:
            raise ValueError("Invalid input type")
        
        # R-F-008: analysis is a pure function of (url, branch, commit) — Constitution
        # Art. 14 (idempotent). Resolve the branch head cheaply (git ls-remote) and reuse a
        # DNA already produced for that exact commit; a new commit is a new key, so the
        # cache can never serve stale results. Opt out with {"cache": False}.
        use_cache = input_data.get("cache", True) if isinstance(input_data, dict) else True
        revision = self._remote_revision(url, branch) if use_cache else None
        cache_key = (url, branch, revision)
        cache = self.__dict__.setdefault("_dna_cache", {})
        if revision and cache_key in cache:
            print(f"[CAPABILITY] Reusing DNA of {url}@{revision[:12]} (same commit)")
            return copy.deepcopy(cache[cache_key])
        
        # Import provider here to avoid circular imports
        from providers import LocalRepositoryProvider
        provider = LocalRepositoryProvider()
        
        # Step 1: Clone
        print(f"[CAPABILITY] Cloning {url}")
        clone_result = provider._clone(RepositoryAnalysisInput(url, branch))
        repo_path = clone_result.path
        
        try:
            # Step 2: Read
            print(f"[CAPABILITY] Reading repository")
            from providers import ReadRepositoryInput
            read_result = provider._read(ReadRepositoryInput(repo_path))
            snapshot = read_result.snapshot
            
            # Step 3 & 4: Detect (inline for now)
            print(f"[CAPABILITY] Detecting languages")
            languages = self._detect_languages(snapshot)
            print(f"[CAPABILITY] Detecting frameworks")
            stack = self._detect_stack(snapshot)
            frameworks = stack.frameworks
            
            # Step 5: Generate DNA
            print(f"[CAPABILITY] Generating DNA")
            dna = self._generate_dna(snapshot, languages, frameworks, stack=stack)
            dna.framework_evidence = [e.to_dict() for e in stack.evidence]
            dna.runtimes = list(stack.runtimes)
            if revision:
                cache[cache_key] = copy.deepcopy(dna)
            
            return dna
            
        finally:
            # Cleanup
            if os.path.exists(repo_path):
                import shutil
                parent = os.path.dirname(repo_path)
                if os.path.exists(parent):
                    shutil.rmtree(parent, ignore_errors=True)
    
    @staticmethod
    def _remote_revision(url: str, branch: str) -> Optional[str]:
        """Commit id at the head of ``branch`` in ``url``, or ``None`` if it cannot be read."""
        try:
            out = subprocess.run(["git", "ls-remote", url, f"refs/heads/{branch}"],
                                 capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0 or not out.stdout.strip():
            return None
        sha = out.stdout.split()[0]
        return sha if len(sha) >= 40 else None
    
    def _detect_languages(self, snapshot: RepositorySnapshot) -> List[str]:
        """Detect programming languages."""
        languages = set()
        
        # Language patterns
        patterns = {
            "Python": [".py", "requirements.txt", "setup.py", "pyproject.toml"],
            "JavaScript": [".js", ".jsx", "package.json"],
            "TypeScript": [".ts", ".tsx", "tsconfig.json"],
            "Java": [".java", "pom.xml", "build.gradle"],
            "Go": [".go", "go.mod", "go.sum"],
            "Rust": [".rs", "Cargo.toml", "Cargo.lock"],
            "C": [".c", ".h"],
            "C++": [".cpp", ".hpp", ".cc"],
            "C#": [".cs", ".csproj", ".sln"],
            "Ruby": [".rb", "Gemfile", "Gemfile.lock"],
            "PHP": [".php", "composer.json"],
            "Swift": [".swift", "Package.swift"],
            "Kotlin": [".kt", "build.gradle.kts"],
            "Scala": [".scala", "build.sbt"],
            "Dart": [".dart", "pubspec.yaml"],
        }
        
        for file_node in snapshot.files:
            if file_node.is_dir:
                continue
            path = file_node.path.lower()
            for lang, exts in patterns.items():
                for ext in exts:
                    if path.endswith(ext.lower()):
                        languages.add(lang)
                        break
        
        return sorted(list(languages))
    
    @staticmethod
    def _manifest_files(snapshot: RepositorySnapshot) -> Dict[str, Optional[str]]:
        """{relative path: content} for dependency manifests only (R-W2-001)."""
        from stack_detection import is_manifest
        return {f.path: f.content for f in snapshot.files
                if not f.is_dir and is_manifest(f.path)}
    
    def _detect_stack(self, snapshot: RepositorySnapshot):
        """Full stack report (frameworks + evidence + runtimes) from manifests only."""
        from stack_detection import detect_stack
        return detect_stack(self._manifest_files(snapshot))
    
    def _detect_frameworks(self, snapshot: RepositorySnapshot) -> List[str]:
        """Detect frameworks from dependency manifests, never from file text (R-W2-001).
        
        A framework is reported only when it is a runtime/peer dependency in a real
        manifest (requirements*.txt, pyproject.toml, setup.cfg/py, Pipfile, package.json,
        Gemfile, composer.json, pom.xml, build.gradle). See ``stack_detection``.
        """
        return self._detect_stack(snapshot).frameworks
    
    def _detect_frameworks_by_text(self, snapshot: RepositorySnapshot) -> List[str]:
        """Legacy text matcher (kept for reference, NOT used — R-W2-001).

        It matched framework names anywhere in any file, so a README mentioning
        express/flask/vue made all of them "detected" and psf/requests came out as
        ``Express, Flask, Next.js, Vue`` (docs/audit/AUDIT-2026-10-21.md §3.6).
        """
        frameworks = set()
        
        framework_patterns = {
            "Django": ["django", "django.db"],
            "Flask": ["flask", "from flask import"],
            "FastAPI": ["fastapi", "uvicorn"],
            "React": ["react", "react-dom"],
            "Vue": ["vue", "@vue"],
            "Angular": ["@angular/core"],
            "Next.js": ["next", "next.config"],
            "Express": ["express"],
            "Spring": ["org.springframework"],
            "Rails": ["rails"],
            "Laravel": ["laravel"],
            "FastAPI": ["fastapi"],
            "PyTorch": ["torch", "import torch"],
            "TensorFlow": ["tensorflow", "import tensorflow"],
            "LangChain": ["langchain"],
            "LlamaIndex": ["llama_index", "llamaindex"],
        }
        
        for file_node in snapshot.files:
            if file_node.is_dir or not file_node.content:
                continue
            
            content = file_node.content
            path = file_node.path.lower()
            
            # Check content
            for framework, keywords in framework_patterns.items():
                for keyword in keywords:
                    if keyword.lower() in content.lower():
                        frameworks.add(framework)
                        break
            
            # Check filenames
            if "package.json" in path:
                frameworks.add("Node.js")
            elif "requirements.txt" in path or "pyproject.toml" in path:
                frameworks.add("Python")
        
        return sorted(list(frameworks))
    
    def _generate_dna(
        self,
        snapshot: RepositorySnapshot,
        languages: List[str],
        frameworks: List[str],
        stack=None,
    ) -> RepositoryDNA:
        """Generate Repository DNA.
        
        ``stack`` is the ``stack_detection.StackReport`` of the snapshot (computed here when
        omitted); dependencies and package managers come from it (R-W2-002).
        """
        metadata = snapshot.metadata
        if stack is None:
            stack = self._detect_stack(snapshot)
        
        # Find README
        readme_summary = ""
        for file_node in snapshot.files:
            if not file_node.is_dir:
                path_lower = file_node.path.lower()
                if "readme" in path_lower and file_node.content:
                    readme_summary = file_node.content[:500]
                    break
        
        # Find license
        license_name = ""
        for file_node in snapshot.files:
            if not file_node.is_dir:
                path_lower = file_node.path.lower()
                if "license" in path_lower or path_lower == "license":
                    license_name = os.path.basename(file_node.path)
                    break
        
        # Find config files
        config_extensions = [
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
            "package.json", "requirements.txt", "Gemfile", "go.mod"
        ]
        config_files = []
        for file_node in snapshot.files:
            if file_node.is_dir:
                continue
            path_lower = file_node.path.lower()
            for ext in config_extensions:
                if path_lower.endswith(ext) or ext in path_lower:
                    config_files.append(file_node.path)
                    break
        
        # Package managers (R-W2-002): from manifests and lock files, never from substrings
        # of arbitrary paths (``node_modules/x/package.json`` is not the project's npm, and
        # Gradle is not Maven).
        from stack_detection import detect_package_managers, dependency_records, project_dependencies
        package_managers = detect_package_managers(
            [f.path for f in snapshot.files if not f.is_dir], self._manifest_files(snapshot))
        
        # Directory tree (top level)
        dirs = set()
        for file_node in snapshot.files:
            if file_node.is_dir:
                parts = file_node.path.split("/")
                if len(parts) > 0:
                    dirs.add(parts[0])
        
        return RepositoryDNA(
            name=metadata.name,
            url=metadata.url,
            owner=metadata.owner,
            primary_language=languages[0] if languages else "",
            languages=languages,
            frameworks=frameworks,
            package_managers=sorted(list(package_managers)),
            dependencies=project_dependencies(stack),
            dependency_details=dependency_records(stack),
            config_files=config_files[:20],  # Limit to 20
            entry_points=[],
            directory_tree=sorted(list(dirs))[:20],
            readme_summary=readme_summary,
            license=license_name,
            generated_at=datetime.now(timezone.utc),
            snapshot_path=""
        )
