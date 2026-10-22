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

# R-W2-007: re-export the seven real capabilities so AutoDiscovery registers them
# from the package root (they are mission-resolvable by name).
from .foundation_extra import (  # noqa: F401 — public re-exports (G2)
    ConfigurationAnalysisCapability,
    DocumentationAnalysisCapability,
    EngineeringKnowledgeExtractionCapability,
    InfrastructureAnalysisCapability,
    LicenseAnalysisCapability,
    RepositoryDNAGenerationCapability,
    SecurityScanCapability,
)
# R-W2-012: the capability genome — mission-resolvable by name from the package root
from .genome import CapabilityGenomeCapability  # noqa: F401 — public re-export (G2)
# R-W2-013: RPP — the 8-stage repository processing pipeline over the unified line
from .rpp import RepositoryProcessingPipelineCapability  # noqa: F401 — public re-export (G2)


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
        """Execute the capability.
        
        ``input_data`` may carry ``tree_depth`` (default 3, R-W2-004): the depth of the
        DNA's ``directory_tree``. It is part of the cache key — the same commit analyzed
        at two depths produces two different DNAs, never a stale reuse.
        """
        if isinstance(input_data, dict):
            url = input_data.get("url", "")
            branch = input_data.get("branch", "main")
            tree_depth = input_data.get("tree_depth", 3)
        elif hasattr(input_data, "url"):
            url = input_data.url
            branch = input_data.branch
            tree_depth = getattr(input_data, "tree_depth", 3)
        else:
            raise ValueError("Invalid input type")
        
        # R-F-008: analysis is a pure function of (url, branch, commit) — Constitution
        # Art. 14 (idempotent). Resolve the branch head cheaply (git ls-remote) and reuse a
        # DNA already produced for that exact commit; a new commit is a new key, so the
        # cache can never serve stale results. Opt out with {"cache": False}.
        use_cache = input_data.get("cache", True) if isinstance(input_data, dict) else True
        revision = self._remote_revision(url, branch) if use_cache else None
        cache_key = (url, branch, revision, tree_depth)
        cache = self.__dict__.setdefault("_dna_cache", {})
        if revision and cache_key in cache:
            print(f"[CAPABILITY] Reusing DNA of {url}@{revision[:12]} (same commit)")
            return self._with_optional_graph(copy.deepcopy(cache[cache_key]), input_data)
        
        # R-W2-006 (ADR-0005): الخط الواحد — التحليل عبر الخدمة المشتركة،
        # و``execute`` إسقاط فوق حقائقها. الحقائق تكتمل في الخدمة قبل تنظيف المستنسخ.
        from capabilities.analysis_service import get_analysis_service
        shared = get_analysis_service().analyze_url(url, branch)
        print(f"[CAPABILITY] Generating DNA")
        dna = self._build_dna(
            meta=shared.meta,
            file_paths=[f.path for f in shared.files if not f.is_dir],
            dir_paths=[f.path for f in shared.files if f.is_dir],
            contents=shared.contents,
            languages=[stat.language for stat in shared.code_languages.values()],
            stack=shared.stack,
            language_stats=self._language_breakdown_of(shared),
            tree_depth=tree_depth,
        )
        dna.framework_evidence = [e.to_dict() for e in shared.stack.evidence]
        dna.runtimes = list(shared.stack.runtimes)
        if revision:
            cache[cache_key] = copy.deepcopy(dna)
        
        return self._with_optional_graph(dna, input_data)
    
    @staticmethod
    def _with_optional_graph(dna: RepositoryDNA, input_data: Any) -> RepositoryDNA:
        """R-W2-008: when the caller asks for a knowledge graph, fill it from this
        analysis and save it — same behavior on a fresh analysis and a cache hit.

        ``knowledge_graph_path`` in the input dict is the save path; without it the
        capability is unchanged for every existing caller.
        """
        if not (isinstance(input_data, dict)
                and input_data.get("knowledge_graph_path")):
            return dna
        from agos_kernel.civilization.knowledge_graph.analysis_loader import fill_and_save
        path = input_data["knowledge_graph_path"]
        report = fill_and_save(dna, path)
        print(f"[CAPABILITY] Knowledge graph of {dna.name} saved to: {path} "
              f"({report.nodes_added} nodes, {report.relationships_added} "
              f"relationships, {len(report.gaps)} named gaps)")
        return dna
    
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
        """Detect programming languages, weighted by lines and files (R-W2-003).

        Delegates to the kernel's ``stack_detection`` (the single source): the returned
        list is ordered by weight — lines first, then files, then name — so
        ``languages[0]`` is the primary language. Manifest names (package.json, go.mod, …)
        are not languages; only code files count.
        """
        from stack_detection import language_weights
        weights = language_weights(
            {f.path: f.content for f in snapshot.files if not f.is_dir})
        return [stat.language for stat in weights.values()]
    
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
    
    def _language_breakdown_of(self, shared) -> Dict[str, Dict[str, int]]:
        """``stack_detection.language_breakdown`` فوق حقائق الخدمة المشتركة —
        غير المقروء يدخل بقيمة None كما في المسار القديم تماماً."""
        from stack_detection import language_breakdown
        return language_breakdown(
            {f.path: shared.contents.get(f.path)
             for f in shared.files if not f.is_dir})
    
    def _generate_dna(
        self,
        snapshot: RepositorySnapshot,
        languages: List[str],
        frameworks: List[str],
        stack=None,
        language_stats: Optional[Dict[str, Dict[str, int]]] = None,
        tree_depth: int = 3,
    ) -> RepositoryDNA:
        """Generate Repository DNA (غلاف توافق فوق الحقائق — G2).
        
        ``stack`` is the ``stack_detection.StackReport`` of the snapshot (computed here when
        omitted); dependencies and package managers come from it (R-W2-002).
        ``language_stats`` is the ``stack_detection.language_breakdown`` of the snapshot
        (computed here when omitted); the primary language is the one with the most lines,
        not the alphabetically first entry (R-W2-003).
        Entry points, the directory tree (depth adjustable via ``tree_depth``, R-W2-004) and
        config files all come from ``stack_detection`` too — one source for the DNA.
        """
        if stack is None:
            stack = self._detect_stack(snapshot)
        if language_stats is None:
            from stack_detection import language_breakdown
            language_stats = language_breakdown(
                {f.path: f.content for f in snapshot.files if not f.is_dir})
        return self._build_dna(
            meta={"name": snapshot.metadata.name, "url": snapshot.metadata.url,
                  "owner": snapshot.metadata.owner},
            file_paths=[f.path for f in snapshot.files if not f.is_dir],
            dir_paths=[f.path for f in snapshot.files if f.is_dir],
            contents={f.path: f.content for f in snapshot.files
                      if not f.is_dir and f.content is not None},
            languages=languages,
            stack=stack,
            language_stats=language_stats,
            tree_depth=tree_depth,
            frameworks=frameworks,
        )
    
    def _build_dna(
        self,
        *,
        meta: Dict[str, str],
        file_paths: List[str],
        dir_paths: List[str],
        contents: Dict[str, str],
        languages: List[str],
        stack,
        language_stats: Dict[str, Dict[str, int]],
        tree_depth: int = 3,
        frameworks: Optional[List[str]] = None,
    ) -> RepositoryDNA:
        """الإسقاط: DNA النواة من الحقائق المشتركة (R-W2-006 — ADR-0005).
        
        دخول صرف فوق الحقائق — لا يفتح مساراً حُذف ولا يعيد مسحاً: readme/license
        من المسارات والمحتوى، وentry points/الشجرة/المديرين/الاعتماديات من
        ``stack_detection`` فوق الفهرس والملفات البيانية. ``frameworks`` تُمرّر
        صراحةً إن مررها المستدعي (سلوك _generate_dna القديم)، وإلا فهي من تقرير
        المكدس نفسه (المصدر الواحد).
        """
        
        # Find README
        readme_summary = ""
        for file_path in file_paths:
            path_lower = file_path.lower()
            if "readme" in path_lower and contents.get(file_path):
                readme_summary = contents[file_path][:500]
                break
        
        # Find license
        license_name = ""
        for file_path in file_paths:
            path_lower = file_path.lower()
            if "license" in path_lower or path_lower == "license":
                license_name = os.path.basename(file_path)
                break
        
        # R-W2-004: config files by suffix or exact name (no substring matching),
        # entry points (conventional + manifest-declared) and the directory tree at an
        # adjustable depth — all from the kernel's single source.
        from stack_detection import detect_config_files, detect_entry_points, directory_tree
        config_files = detect_config_files(file_paths)
        
        # Package managers (R-W2-002): from manifests and lock files, never from substrings
        # of arbitrary paths (``node_modules/x/package.json`` is not the project's npm, and
        # Gradle is not Maven).
        from stack_detection import detect_package_managers, dependency_records, project_dependencies
        manifests = {p: contents.get(p) for p in file_paths if self._is_manifest_path(p)}
        package_managers = detect_package_managers(file_paths, manifests)
        
        entry_points = detect_entry_points(file_paths, manifests)
        tree = directory_tree(file_paths, max_depth=tree_depth, dir_paths=dir_paths)
        
        return RepositoryDNA(
            name=meta.get("name", ""),
            url=meta.get("url", ""),
            owner=meta.get("owner", ""),
            primary_language=languages[0] if languages else "",
            languages=languages,
            frameworks=list(frameworks) if frameworks is not None else list(stack.frameworks),
            package_managers=sorted(list(package_managers)),
            dependencies=project_dependencies(stack),
            dependency_details=dependency_records(stack),
            config_files=config_files,
            entry_points=entry_points,
            directory_tree=tree,
            readme_summary=readme_summary,
            license=license_name,
            generated_at=datetime.now(timezone.utc),
            snapshot_path="",
            language_stats=language_stats,
        )
    
    @staticmethod
    def _is_manifest_path(path: str) -> bool:
        """Is this file path a dependency manifest? (stack_detection — المصدر الواحد)."""
        from stack_detection import is_manifest
        return is_manifest(path)
