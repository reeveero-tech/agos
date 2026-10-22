"""RIE Application - Pipeline orchestration and feature aggregation."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

# R-F-006: relative imports — rie works as `rie`, `agos.rie` and under any sys.path root
from ..contracts import DetectorResult, RepositoryDNA, RepositoryFeatureSet
from ..detectors import DetectorContext, DetectorRegistry, create_default_registry
from ..infrastructure import GitFetcher, FileSystemReader, RepositoryNormalizer


@dataclass
class FeatureAggregator:
    """
    Aggregates detector results into unified feature set.
    
    Rules:
    ✅ No Duplicate Features
    ✅ No Conflicts
    ✅ Typed Objects Only
    """
    
    def aggregate(self, repository_url: str, results: List[DetectorResult]) -> RepositoryFeatureSet:
        """Aggregate detector results."""
        features = RepositoryFeatureSet(repository_url=repository_url)
        
        for result in results:
            if not result.success:
                continue
            
            self._merge_features(features, result.features)
        
        # Validate
        features.is_valid = self._validate(features)
        
        return features
    
    def _merge_features(self, features: RepositoryFeatureSet, detector_features: Dict[str, Any]) -> None:
        """Merge features from a detector."""
        # Languages
        if "languages" in detector_features:
            for lang in detector_features["languages"]:
                if lang not in features.languages:
                    features.languages[lang] = 0
        
        if "language_percentages" in detector_features:
            features.languages.update(detector_features["language_percentages"])
        
        if "primary_language" in detector_features:
            features.languages = detector_features.get("language_percentages", {})
        
        # R-W2-003: per-language weights (files + lines) from the LanguageDetector
        if "language_stats" in detector_features:
            for lang, stat in detector_features["language_stats"].items():
                features.language_stats[lang] = {"files": stat.get("files", 0), "lines": stat.get("lines", 0)}
        
        # Frameworks
        if "frameworks" in detector_features:
            for fw in detector_features["frameworks"]:
                if fw not in features.frameworks:
                    features.frameworks.append(fw)
        
        # Dependencies
        if "dependencies" in detector_features:
            for dep in detector_features["dependencies"]:
                if dep not in features.dependencies:
                    features.dependencies.append(dep)
        
        # Package managers
        if "dependency_details" in detector_features:  # R-W2-002
            for rec in detector_features["dependency_details"]:
                if rec not in features.dependency_details:
                    features.dependency_details.append(rec)
        
        if "package_managers" in detector_features:
            for pm in detector_features["package_managers"]:
                if pm not in features.package_managers:
                    features.package_managers.append(pm)
        
        # Config files
        if "config_files" in detector_features:
            for cf in detector_features["config_files"]:
                if cf not in features.config_files:
                    features.config_files.append(cf)
        
        # Entry points
        if "entry_points" in detector_features:
            for ep in detector_features["entry_points"]:
                if ep not in features.entry_points:
                    features.entry_points.append(ep)
        
        # Directory tree
        if "directory_tree" in detector_features:
            for d in detector_features["directory_tree"]:
                if d not in features.directory_tree:
                    features.directory_tree.append(d)
        
        # Documentation
        if "has_license" in detector_features:
            features.has_license = detector_features["has_license"]
        if "license_type" in detector_features:
            features.license_type = detector_features["license_type"]
        if "has_readme" in detector_features:
            features.has_readme = detector_features["has_readme"]
        if "has_changelog" in detector_features:
            features.has_changelog = detector_features["has_changelog"]
        
        # Statistics
        if "total_files" in detector_features:
            features.total_files = detector_features["total_files"]
        if "total_directories" in detector_features:
            features.total_directories = detector_features["total_directories"]
    
    def _validate(self, features: RepositoryFeatureSet) -> bool:
        """Validate aggregated features."""
        errors = []
        
        # Check for required features
        if not features.languages:
            errors.append("No languages detected")
        
        # Check for duplicates
        if len(features.frameworks) != len(set(features.frameworks)):
            errors.append("Duplicate frameworks detected")
        
        if len(features.package_managers) != len(set(features.package_managers)):
            errors.append("Duplicate package managers detected")
        
        features.validation_errors = errors
        return len(errors) == 0


class RepositoryIntelligencePipeline:
    """
    RIE Pipeline.
    
    Pipeline:
    1. Fetch
    2. Normalize
    3. Discover
    4. Detect
    5. Extract
    6. Analyze
    7. Validate
    8. Generate DNA
    """
    
    def __init__(self, detector_registry: DetectorRegistry = None):
        self.fetcher = GitFetcher()
        self.reader = FileSystemReader()
        self.normalizer = RepositoryNormalizer(self.fetcher, self.reader)
        self.detector_registry = detector_registry or create_default_registry()
        self.aggregator = FeatureAggregator()
    
    def execute(self, url: str, branch: str = "main") -> RepositoryDNA:
        """Execute the complete pipeline.

        R-W2-006 (ADR-0005): الخط الواحد — الجلب والقراءة عبر الخدمة
        المشتركة (مصدر URL بسياسة النواة R-W2-004/005 نفسها)، و``normalized``
        يُبنى من حقائقها، والكاشفون يعملون فوقها في الذاكرة — الحقائق تكتمل
        قبل تنظيف المستنسخ داخل الخدمة. توثيق توحيد سلوكي: فهرس مصدر URL
        الآن بسياسة النواة (لا يستثني node_modules مثلاً) — نفس حقائق DNA
        النواة للـURL نفسه.
        """
        start_time = datetime.now(timezone.utc)
        
        # Step 1-2: الخط الواحد — Fetch + Normalize عبر الخدمة المشتركة
        print(f"[RIE] Fetching repository: {url}")
        from agos_kernel.capabilities.analysis_service import get_analysis_service
        shared = get_analysis_service().analyze_url(url, branch)
        normalized = self._normalized_from_shared(shared, url, branch)
        
        # Create detector context
        files_with_content = {}
        for path, data in normalized.get("files", {}).items():
            files_with_content[path] = {
                "size": data.get("size", 0),
                "extension": data.get("extension", ""),
                "has_content": data.get("has_content", False)
            }
        
        context = DetectorContext(
            repository_url=url,
            files=files_with_content,
            directories=normalized.get("directories", []),
            metadata=normalized
        )
        
        # Step 3-6: Detect
        print("[RIE] Running detectors")
        detector_results = self.detector_registry.detect_all(context)
        
        # Step 7: Aggregate
        print("[RIE] Aggregating features")
        feature_set = self.aggregator.aggregate(url, detector_results)
        
        # Step 8: Generate DNA
        print("[RIE] Generating DNA")
        dna = self._generate_dna(normalized, feature_set, detector_results)
        
        end_time = datetime.now(timezone.utc)
        dna.metadata = {
            "pipeline_duration_ms": int((end_time - start_time).total_seconds() * 1000),
            "detectors_run": len(detector_results)
        }
        
        return dna
    
    @staticmethod
    def _normalized_from_shared(shared, url: str, branch: str) -> Dict[str, Any]:
        """إسقاط ``normalized`` القديم من حقائق الخدمة المشتركة — نفس الشكل
        الذي كان ينتجه ``RepositoryNormalizer.normalize`` (المصدر واحد الآن)."""
        from ..detectors import _stack_detection
        sd = _stack_detection()
        is_manifest = sd.is_manifest
        is_code_ext = {ext for exts in sd.LANGUAGE_EXTENSIONS.values() for ext in exts}
        
        non_dir = [f for f in shared.files if not f.is_dir]
        # محتوى الملفات البيانية وملفات الشيفرة المقروءة — للكاشفين
        manifest_content = {
            f.path: shared.contents[f.path]
            for f in non_dir
            if f.path in shared.contents
            and (is_manifest(f.path) or f.extension in is_code_ext)
        }
        return {
            "_content": manifest_content,
            "url": url,
            "name": shared.meta.get("name", ""),
            "owner": shared.meta.get("owner", ""),
            # الفرع الفعلي من الحقائق (بعد تراجع clone_safety) لا المعامل
            "branch": shared.source_branch or branch,
            "commit": shared.source_commit,
            "directories": sorted(f.path for f in shared.files if f.is_dir),
            "files": {
                f.path: {
                    "size": f.size_bytes,
                    "extension": f.extension,
                    "has_content": f.path in shared.contents,
                }
                for f in non_dir
            },
            "total_files": len(non_dir),
            "total_directories": sum(1 for f in shared.files if f.is_dir),
        }
    
    def _generate_dna(
        self,
        normalized: Dict[str, Any],
        features: RepositoryFeatureSet,
        results: List[DetectorResult]
    ) -> RepositoryDNA:
        """Generate Repository DNA from features."""
        # Get primary language
        primary_lang = ""
        if features.languages:
            primary_lang = max(features.languages, key=features.languages.get)
        
        # Get language list
        languages = list(features.languages.keys())
        
        return RepositoryDNA(
            id=normalized.get("commit", ""),
            name=normalized.get("name", ""),
            url=normalized.get("url", ""),
            owner=normalized.get("owner", ""),
            branch=normalized.get("branch", "main"),
            commit=normalized.get("commit", ""),
            primary_language=primary_lang,
            languages=languages,
            frameworks=features.frameworks,
            package_managers=features.package_managers,
            dependencies=features.dependencies,
            dependency_details=list(features.dependency_details),
            # R-W2-003: per-language weights (files + lines) — lines are the weight.
            language_stats=dict(features.language_stats),
            config_files=features.config_files,
            entry_points=features.entry_points,
            directory_tree=features.directory_tree,
            readme_summary="",
            license=features.license_type,
            has_documentation=features.has_readme,
            total_files=features.total_files or normalized.get("total_files", 0),
            total_directories=features.total_directories or len(features.directory_tree),
            generated_at=datetime.now(timezone.utc)
        )


def create_rie_pipeline() -> RepositoryIntelligencePipeline:
    """Create RIE pipeline with default configuration."""
    return RepositoryIntelligencePipeline()
