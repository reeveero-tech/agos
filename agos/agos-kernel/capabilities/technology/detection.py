"""Technology Detection Capability."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Set


@dataclass
class TechnologyDetection:
    """Technology detection result."""
    id: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    build_systems: List[str] = field(default_factory=list)
    containers: List[str] = field(default_factory=list)
    cloud_providers: List[str] = field(default_factory=list)
    confidence: float = 1.0
    # R-W2-001: why each framework is (or is not) reported, and which manifests were read.
    framework_evidence: List[Dict[str, Any]] = field(default_factory=list)
    manifests_read: List[str] = field(default_factory=list)


LANGUAGE_PATTERNS = {
    "Python": [".py", "requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
    "JavaScript": [".js", ".jsx", "package.json", "node_modules"],
    "TypeScript": [".ts", ".tsx", "tsconfig.json"],
    "Java": [".java", "pom.xml", "build.gradle", "gradlew"],
    "Go": [".go", "go.mod", "go.sum"],
    "Rust": [".rs", "Cargo.toml", "Cargo.lock"],
    "C": [".c", ".h", "CMakeLists.txt"],
    "C++": [".cpp", ".hpp", ".cc", ".cxx"],
    "C#": [".cs", ".csproj", ".sln", "NuGet.Config"],
    "Ruby": [".rb", "Gemfile", "Gemfile.lock", "Rakefile"],
    "PHP": [".php", "composer.json", "composer.lock"],
    "Swift": [".swift", "Package.swift", ".xcodeproj"],
    "Kotlin": [".kt", ".kts", "build.gradle.kts"],
    "Scala": [".scala", "build.sbt"],
    "Dart": [".dart", "pubspec.yaml"],
    "Shell": [".sh", ".bash", ".zsh"],
    "HTML": [".html", ".htm"],
    "CSS": [".css", ".scss", ".sass", ".less"],
}

# Historical path patterns (kept for reference; R-W2-001: a path is not evidence of a
# framework — "app.py" is not Flask, "pages/" is not Next.js). Frameworks are decided by
# ``stack_detection`` from manifest contents passed to ``execute(..., contents=...)``.
FRAMEWORK_PATTERNS = {
    "Django": ["django", "settings.py"],
    "Flask": ["flask", "app.py"],
    "FastAPI": ["fastapi", "uvicorn"],
    "Express": ["express", "app.js"],
    "React": ["react", "react-dom", "jsx", "tsx"],
    "Vue": ["vue", "@vue"],
    "Angular": ["@angular/core"],
    "Next.js": ["next.config", "pages/", "app/"],
    "Spring": ["org.springframework", "application.properties"],
    "Rails": ["Rails", "config/routes.rb"],
    "Laravel": ["laravel", "artisan"],
    "DotNet": [".csproj", "Program.cs"],
    "Flutter": ["flutter:", "pubspec.yaml"],
    "PyTorch": ["torch", "import torch"],
    "TensorFlow": ["tensorflow", "import tensorflow"],
    "LangChain": ["langchain"],
}

PACKAGE_MANAGERS = {
    "pip": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
    "npm": ["package.json", "package-lock.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "go": ["go.mod", "go.sum"],
    "cargo": ["Cargo.toml", "Cargo.lock"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
    "bundler": ["Gemfile", "Gemfile.lock"],
    "composer": ["composer.json", "composer.lock"],
    "nuget": ["packages.config", "*.nupkg"],
}

CONTAINERS = {
    "Docker": ["Dockerfile", "docker-compose.yml", ".dockerignore"],
    "Kubernetes": ["kubernetes/", "k8s/", "*.yaml", "*.yml"],
    "Helm": ["Chart.yaml", "values.yaml"],
}

CLOUD_PROVIDERS = {
    "AWS": ["aws/", ".aws/", "aws_credentials"],
    "GCP": ["gcp/", ".gcp/"],
    "Azure": ["azure/", ".azure/"],
    "Vercel": ["vercel.json", ".vercel"],
    "Netlify": ["netlify.toml"],
}


class TechnologyDetectionCapability:
    """Detect technologies in a repository."""
    
    def __init__(self):
        """Initialize capability."""
        self.name = "TechnologyDetection"
        self.version = "1.0.0"
    
    def execute(self, file_paths: List[str],
                contents: Optional[Mapping[str, Optional[str]]] = None) -> TechnologyDetection:
        """Detect technologies from file paths.

        Frameworks need evidence (R-W2-001): pass ``contents`` = {path: text} for the
        dependency manifests. With paths alone no framework is claimed.
        """
        detection = TechnologyDetection(id=str(uuid.uuid4()))
        
        paths_lower = [p.lower() for p in file_paths]
        
        # Detect languages
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if any(pattern.lower() in p for p in paths_lower):
                    detection.languages.append(lang)
                    break
        
        # Detect frameworks — from manifest contents only (R-W2-001)
        try:
            from agos.kernel import stack_detection
        except ImportError:
            import stack_detection
        manifests = {p: (contents or {}).get(p) for p in file_paths
                     if stack_detection.is_manifest(p) and (contents or {}).get(p) is not None}
        stack = stack_detection.detect_stack(manifests)
        detection.frameworks.extend(stack.frameworks)
        detection.framework_evidence = [e.to_dict() for e in stack.evidence]
        detection.manifests_read = list(stack.manifests)
        
        # Detect package managers
        for pm, patterns in PACKAGE_MANAGERS.items():
            for pattern in patterns:
                if any(pattern.lower() in p for p in paths_lower):
                    detection.package_managers.append(pm)
                    break
        
        # Detect containers
        for container, patterns in CONTAINERS.items():
            for pattern in patterns:
                if any(pattern.lower() in p for p in paths_lower):
                    detection.containers.append(container)
                    break
        
        # Detect cloud providers
        for provider, patterns in CLOUD_PROVIDERS.items():
            for pattern in patterns:
                if any(pattern.lower() in p for p in paths_lower):
                    detection.cloud_providers.append(provider)
                    break
        
        # Deduplicate
        detection.languages = list(set(detection.languages))
        detection.frameworks = list(set(detection.frameworks))
        detection.package_managers = list(set(detection.package_managers))
        detection.containers = list(set(detection.containers))
        detection.cloud_providers = list(set(detection.cloud_providers))
        
        return detection