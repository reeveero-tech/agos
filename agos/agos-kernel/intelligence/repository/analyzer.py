"""Repository Analyzer - Analyzes repository structure and detects technologies."""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    Language, Framework, BuildSystem, ContainerTech, CloudProvider,
    Database, Queue, DirectoryNode, Module, RepositoryGenome, RepositoryMetrics,
    FileMetrics
)


class RepositoryAnalyzer:
    """Analyzes repository structure and technologies."""
    
    # File extension to language mapping
    EXTENSION_MAP = {
        '.py': Language.PYTHON,
        '.js': Language.JAVASCRIPT,
        '.ts': Language.TYPESCRIPT,
        '.tsx': Language.TYPESCRIPT,
        '.jsx': Language.JAVASCRIPT,
        '.java': Language.JAVA,
        '.kt': Language.KOTLIN,
        '.swift': Language.SWIFT,
        '.go': Language.GO,
        '.rs': Language.RUST,
        '.c': Language.C,
        '.cpp': Language.CPP,
        '.cc': Language.CPP,
        '.cs': Language.CSHARP,
        '.rb': Language.RUBY,
        '.php': Language.PHP,
        '.scala': Language.SCALA,
        '.hs': Language.HASKELL,
        '.sh': Language.SHELL,
        '.bash': Language.SHELL,
        '.zsh': Language.SHELL,
        '.dockerfile': Language.DOCKERFILE,
        'Dockerfile': Language.DOCKERFILE,
    }
    
    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        Framework.DJANGO: ['settings.py', 'manage.py', 'django'],
        Framework.FLASK: ['flask', 'app.route', '@app.route'],
        Framework.FASTAPI: ['fastapi', 'uvicorn'],
        Framework.REACT: ['react', 'React', 'create-react-app'],
        Framework.VUE: ['vue', 'Vue', 'vue-cli'],
        Framework.ANGULAR: ['angular', '@angular'],
        Framework.NEXTJS: ['next', 'next.config', 'getServerSideProps'],
        Framework.NESTJS: ['@nestjs', 'nest-cli.json'],
        Framework.SPRING: ['spring', 'SpringBootApplication', '@SpringBootApplication'],
        Framework.EXPRESS: ['express', 'express()', 'app.use(express)'],
        Framework.FASTIFY: ['fastify'],
        Framework.GIN: ['gin-gonic', 'gin.Run'],
        Framework.FLUTTER: ['flutter', 'pubspec.yaml'],
    }
    
    # Build system files
    BUILD_FILES = {
        'package.json': (BuildSystem.NPM, 'node_modules'),
        'yarn.lock': (BuildSystem.YARN, 'node_modules'),
        'pnpm-lock.yaml': (BuildSystem.PNPM, 'node_modules'),
        'pyproject.toml': (BuildSystem.POETRY, '__pycache__'),
        'requirements.txt': (BuildSystem.PIP, '__pycache__'),
        'Pipfile': (BuildSystem.PIP, '__pycache__'),
        'pom.xml': (BuildSystem.MAVEN, 'target'),
        'build.gradle': (BuildSystem.GRADLE, 'build'),
        'build.gradle.kts': (BuildSystem.GRADLE, 'build'),
        'Cargo.toml': (BuildSystem.CARGO, 'target'),
        'CMakeLists.txt': (BuildSystem.CMAKE, 'build'),
        'Makefile': (BuildSystem.UNKNOWN, None),
    }
    
    # Test framework patterns
    TEST_PATTERNS = {
        'pytest': ['pytest.ini', 'conftest.py', 'test_', '_test.py'],
        'unittest': ['unittest', 'TestCase'],
        'jest': ['jest.config', '.test.', '.spec.'],
        'mocha': ['mocha', '.spec.', '.test.'],
        'junit': ['junit', 'TestSuite'],
        'rspec': ['rspec', '_spec.rb'],
    }
    
    # CI/CD system files
    CI_FILES = {
        '.github/workflows': 'github_actions',
        '.gitlab-ci.yml': 'gitlab_ci',
        'Jenkinsfile': 'jenkins',
        'Jenkinsfile': 'jenkins',
        '.circleci/config.yml': 'circleci',
        '.travis.yml': 'travis',
        '.bitbucket-pipelines.yml': 'bitbucket_pipelines',
        'azure-pipelines.yml': 'azure_devops',
    }
    
    # Container files
    CONTAINER_FILES = {
        'Dockerfile': ContainerTech.DOCKER,
        'docker-compose.yml': ContainerTech.DOCKER,
        'docker-compose.yaml': ContainerTech.DOCKER,
        'podman.yml': ContainerTech.PODMAN,
        'kubernetes/': ContainerTech.KUBERNETES,
        'k8s/': ContainerTech.KUBERNETES,
        'Chart.yaml': ContainerTech.HELM,
    }
    
    # Cloud provider indicators
    CLOUD_FILES = {
        'aws/': CloudProvider.AWS,
        '.aws/': CloudProvider.AWS,
        'azure/': CloudProvider.AZURE,
        '.azure/': CloudProvider.AZURE,
        'gcp/': CloudProvider.GCP,
        '.gcp/': CloudProvider.GCP,
        'vercel.json': CloudProvider.VERCEL,
        'netlify.toml': CloudProvider.UNKNOWN,  # Generic
        'Procfile': CloudProvider.HEROKU,
    }
    
    # Database indicators
    DB_PATTERNS = {
        'postgresql': ['postgres', 'postgresql', 'psycopg2'],
        'mysql': ['mysql', 'mysql2'],
        'mongodb': ['mongodb', 'mongoose', 'pymongo'],
        'redis': ['redis', 'ioredis', 'redis-py'],
        'elasticsearch': ['elasticsearch', 'elastic'],
        'cassandra': ['cassandra', 'scylla'],
        'neo4j': ['neo4j', 'py2neo'],
    }
    
    # Queue indicators
    QUEUE_PATTERNS = {
        'rabbitmq': ['amqp', 'pika', 'rabbitmq'],
        'kafka': ['kafka', 'confluent-kafka', 'kafka-python'],
        'sqs': ['boto3', 'sqs'],
        'nats': ['nats', 'nats-py'],
    }
    
    # Config file patterns
    CONFIG_PATTERNS = [
        r'\.json$', r'\.yaml$', r'\.yml$', r'\.toml$', r'\.ini$',
        r'\.conf$', r'\.config$', r'\.env$', r'\.editorconfig$',
        r'\.prettierrc', r'\.eslintrc', r'\.babelrc', r'\.webpack'
    ]
    
    # Directories to ignore
    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', '.pytest_cache',
        '.mypy_cache', '.venv', 'venv', 'env', '.venv',
        'dist', 'build', 'target', '.idea', '.vscode',
        '.sass-cache', '.next', '.nuxt', '.cache'
    }
    
    def __init__(self, root_path: str):
        """Initialize analyzer with repository root path."""
        self.root_path = Path(root_path)
        self.genome = RepositoryGenome(
            name=self.root_path.name,
            path=str(self.root_path),
            root_path=str(self.root_path)
        )
    
    def analyze(self) -> RepositoryGenome:
        """Run complete analysis.

        R-W2-006 (ADR-0005): الخط الواحد — مسح واحد عبر الخدمة المشتركة،
        وكل الاكتشافات إسقاطات فوق الفهرس والمحتوى المقروء (لا ``os.walk``
        مستقلاً لكل مرحلة). اللقطة تُصفّر في بداية كل ``analyze()`` فالتعديلات
        على القرص تظهر — لا تخزين مؤقت دائم.
        """
        # لقطة جديدة لكل تحليل — لا كاش دائم (التعديلات تظهر)
        self.__dict__.pop("_shared_analysis", None)

        self._analyze_structure()
        self._detect_languages()
        self._detect_frameworks()
        self._detect_build_systems()
        self._detect_package_managers()
        self._detect_dependencies()
        self._detect_test_frameworks()
        self._detect_ci_cd()
        self._detect_containers()
        self._detect_cloud_providers()
        self._detect_databases()
        self._detect_queues()
        self._calculate_metrics()
        return self.genome
    
    @property
    def _shared(self):
        """حقائق الخدمة المشتركة — لقطة تحليل واحد لا تخزين مؤقت دائم:
        كل ``analyze()`` يبدأ لقطة جديدة (التعديلات على القرص تظهر)، والمقارنة
        بالمسار المحلول فلا يعيد مسار نسبي المسح مرتين.
        """
        resolved = str(Path(self.root_path).resolve())
        cached = self.__dict__.get("_shared_analysis")
        if cached is None or cached.source_path != resolved:
            from agos_kernel.capabilities.analysis_service import (
                ScanPolicy, get_analysis_service)
            self.__dict__["_shared_analysis"] = get_analysis_service().analyze_path(
                resolved,
                policy=ScanPolicy(exclude=lambda name: name in self.IGNORE_DIRS,
                                   classify_big=True))
        return self.__dict__["_shared_analysis"]
    
    def _analyze_structure(self) -> None:
        """Analyze directory structure — إسقاط من فهرس الخدمة (لا مسح ثانٍ).

        نفس دلالات القديم: عقدة جذر (المسار ".")، عقدة لكل مجلد بعمقها،
        وModule لكل ملف بياني بالاسم أيا كان موقعه، و``metrics.depth`` أقصى عمق.
        """
        directories = []
        modules = []
        max_depth = 0
        
        # عقدة الجذر — كما في القديم (المسار النسبي ".")
        directories.append(DirectoryNode(
            path=".", name=self.root_path.name, is_dir=True, depth=0))
        
        for entry in self._shared.files:
            rel_path = entry.path
            if entry.is_dir:
                depth = len(Path(rel_path).parts)
                max_depth = max(max_depth, depth)
                directories.append(DirectoryNode(
                    path=rel_path,
                    name=Path(rel_path).name,
                    is_dir=True,
                    depth=depth
                ))
            else:
                # Classify files — بالاسم أيا كان موقعه (كما في القديم)
                if Path(rel_path).name in ['package.json', 'setup.py', 'pyproject.toml',
                                            'Cargo.toml', 'go.mod', 'pom.xml']:
                    modules.append(Module(
                        path=rel_path,
                        name=Path(rel_path).name,
                        type='root',
                        files=[rel_path]
                    ))
        
        self.genome.directories = directories
        self.genome.modules = modules
        self.genome.metrics.depth = max_depth
    
    def _detect_languages(self) -> None:
        """Detect programming languages, weighted by lines (R-W2-003).

        R-W2-006: إسقاط من فهرس الخدمة — تصنيف ``EXTENSION_MAP`` نفسه، والأسطر
        من إحصاء المسح الواحد (لا قراءة ثانية). ``metrics.languages`` keeps the
        file count per language (existing consumers); ``metrics.language_lines``
        carries the line count — the weight that decides the primary language in
        the DNA (most lines, then most files, then name).
        """
        languages: Dict[str, int] = {}
        language_lines: Dict[str, int] = {}
        
        for entry in self._shared.files:
            if entry.is_dir:
                continue
            lang = self.EXTENSION_MAP.get(entry.extension)
            if lang:
                lang_key = lang.value
                languages[lang_key] = languages.get(lang_key, 0) + 1
                self.genome.source_files.append(entry.path)
                # R-W2-003: أسطر المحتوى المقروء (replace — دلالة القراءة
                # القديمة للغات) — ليس مقاييس التصنيف (ignore)
                if entry.lines >= 0:
                    language_lines[lang_key] = language_lines.get(lang_key, 0) + entry.lines
        
        self.genome.languages = {Language(l) for l in languages.keys()}
        self.genome.metrics.languages = languages
        self.genome.metrics.language_lines = language_lines
    
    def _detect_frameworks(self) -> None:
        """Detect frameworks from dependency manifests only (R-W2-001).

        R-W2-006: تقرير المكدس من الخدمة المشتركة نفسها (المصدر الواحد) —
        لا ``read_manifests`` مستقل. Delegates to the kernel's ``stack_detection``;
        names are mapped onto the ``Framework`` enum, frameworks the enum does
        not model are kept in ``self.framework_evidence`` only.
        """
        stack = self._shared.stack
        detected = set()
        for name in stack.frameworks:
            key = name.lower().replace(".", "").replace(" ", "")
            try:
                detected.add(Framework(key))
            except ValueError:
                continue
        self.framework_evidence = [e.to_dict() for e in stack.evidence]
        self.genome.frameworks = detected
    
    def _detect_frameworks_by_text(self) -> None:
        """Legacy text matcher (kept for reference, NOT used — R-W2-001).

        Any ``.py`` file containing e.g. "next" or "spring" marked the framework as used.
        """
        detected = set()
        
        # Check package.json for JS frameworks
        pkg_json = self.root_path / 'package.json'
        if pkg_json.exists():
            content = pkg_json.read_text()
            for framework, keywords in self.FRAMEWORK_PATTERNS.items():
                if any(k in content for k in keywords):
                    detected.add(framework)
        
        # Check files for Python frameworks
        for root, _, files in os.walk(self.root_path):
            for f in files:
                if f.endswith('.py'):
                    try:
                        content = (Path(root) / f).read_text(errors='ignore')
                        for framework, keywords in self.FRAMEWORK_PATTERNS.items():
                            if any(k in content for k in keywords):
                                detected.add(framework)
                    except:
                        pass
        
        self.genome.frameworks = detected
    
    def _detect_build_systems(self) -> None:
        """Detect build systems — من فهرس الخدمة (ملفات الجذر بالاسم)."""
        detected = set()
        root_names = {Path(f.path).name for f in self._shared.files
                      if not f.is_dir and '/' not in f.path}
        
        for build_file, (system, _) in self.BUILD_FILES.items():
            if build_file in root_names:
                detected.add(system)
        
        self.genome.build_systems = detected
    
    def _detect_package_managers(self) -> None:
        """Detect package managers from manifests and lock files (R-W2-002).
        
        R-W2-006: فوق فهرس الخدمة — المصدر الواحد نفسه (لا مسح قرص مستقل).
        """
        stack_detection = self._stack_detection()
        file_paths = [f.path for f in self._shared.files if not f.is_dir]
        self.genome.package_managers = set(
            stack_detection.detect_package_managers(file_paths, self._shared.manifests))
    
    def _detect_dependencies(self) -> None:
        """Direct runtime/peer dependencies + full records from manifests (R-W2-002).
        
        R-W2-006: من تقرير المكدس المشترك نفسه (لا ``read_manifests`` مستقل).
        """
        stack_detection = self._stack_detection()
        report = self._shared.stack
        self.genome.dependencies = stack_detection.project_dependencies(report)
        self.genome.dependency_details = stack_detection.dependency_records(report)
    
    @staticmethod
    def _stack_detection():
        try:
            from agos.kernel import stack_detection
        except ImportError:
            import stack_detection
        return stack_detection
    
    def _detect_package_managers_by_root_files(self) -> None:
        """Legacy root-file check (kept for reference, NOT used — R-W2-002).

        Any pyproject.toml meant "poetry" and only the repository root was inspected.
        """
        managers = set()
        
        # Python
        if (self.root_path / 'requirements.txt').exists():
            managers.add('pip')
        if (self.root_path / 'pyproject.toml').exists():
            managers.add('poetry')
        
        # JavaScript
        if (self.root_path / 'package.json').exists():
            managers.add('npm')
            if (self.root_path / 'yarn.lock').exists():
                managers.add('yarn')
            if (self.root_path / 'pnpm-lock.yaml').exists():
                managers.add('pnpm')
        
        self.genome.package_managers = managers
    
    def _detect_test_frameworks(self) -> None:
        """Detect test frameworks — من أسماء ملفات الفهرس (لا مسح ثانٍ)."""
        detected = set()
        
        for entry in self._shared.files:
            if entry.is_dir:
                continue
            name = Path(entry.path).name
            for framework, patterns in self.TEST_PATTERNS.items():
                if any(p in name for p in patterns):
                    detected.add(framework)
        
        self.genome.test_frameworks = detected
    
    def _detect_ci_cd(self) -> None:
        """Detect CI/CD systems — من فهرس الخدمة."""
        detected = set()
        index_paths = {f.path for f in self._shared.files}
        
        for path, system in self.CI_FILES.items():
            if path in index_paths:
                detected.add(system)
        
        self.genome.ci_cd_systems = detected
    
    def _detect_containers(self) -> None:
        """Detect container technologies — من فهرس الخدمة. فرع ``rglob``
        القديم (المسار فيه ``/``): مطابقة الاسم في أي عمق؛ وفرع الجذر
        (بلا ``/``): وجود المسار عند الجذر فقط — كما في القديم بالضبط."""
        detected = set()
        all_names = {Path(f.path).name for f in self._shared.files}
        root_paths = {f.path for f in self._shared.files if '/' not in f.path}
        
        for path, tech in self.CONTAINER_FILES.items():
            if '/' in path:
                if path.split('/')[0] in all_names:
                    detected.add(tech)
            else:
                if path in root_paths:
                    detected.add(tech)
        
        self.genome.container_tech = detected
    
    def _detect_cloud_providers(self) -> None:
        """Detect cloud providers — من فهرس الخدمة (فرع الجذر عند الجذر فقط)."""
        detected = set()
        all_names = {Path(f.path).name for f in self._shared.files}
        root_paths = {f.path for f in self._shared.files if '/' not in f.path}
        
        for path, provider in self.CLOUD_FILES.items():
            if '/' in path:
                if path.split('/')[0] in all_names:
                    detected.add(provider)
            else:
                if path in root_paths:
                    detected.add(provider)
        
        self.genome.cloud_providers = detected
    
    def _search_patterns(self, entry, patterns: dict) -> set:
        """بحث الكلمات المفتاحية عبر الخدمة (بحث تدفقي بدفعات ثابتة الذاكرة
        عبر حدود الدفعات — لا سقف قراءة ولا فتح روابط رمزية R-W2-005)."""
        from agos_kernel.capabilities.analysis_service import search_keywords
        if self._shared.unread.get(entry.path) == "symlink":
            return set()   # لا قراءة عبر رابط رمزي — حتى للكشف
        return search_keywords(str(self.root_path / entry.path), patterns)

    def _detect_databases(self) -> None:
        """Detect databases — من محتوى المسح المقروء، والكبير ذو الامتدادات
        المعنية ببحث تدفقي محدود من القرص (المسار محلي دائم — القديم قرأه
        بلا حد؛ هنا قراءة محدودة موثقة)."""
        detected = set()

        for entry in self._shared.files:
            if entry.is_dir or not entry.path.endswith(('.py', '.js', '.ts', '.json')):
                continue
            content = self._shared.contents.get(entry.path)
            if content is None:
                for name in self._search_patterns(entry, self.DB_PATTERNS):
                    detected.add(Database(name))
                continue
            for db, keywords in self.DB_PATTERNS.items():
                if any(k in content.lower() for k in keywords):
                    detected.add(Database(db))

        self.genome.databases = detected

    def _detect_queues(self) -> None:
        """Detect message queues — من محتوى المسح المقروء، والكبير ببحث
        تدفقي محدود من القرص."""
        detected = set()

        for entry in self._shared.files:
            if entry.is_dir or not entry.path.endswith(('.py', '.js', '.ts', '.json')):
                continue
            content = self._shared.contents.get(entry.path)
            if content is None:
                for name in self._search_patterns(entry, self.QUEUE_PATTERNS):
                    detected.add(Queue(name))
                continue
            for queue, keywords in self.QUEUE_PATTERNS.items():
                if any(k in content.lower() for k in keywords):
                    detected.add(Queue(queue))

        self.genome.queues = detected
    
    def _calculate_metrics(self) -> None:
        """Calculate repository metrics — من تصنيف المسح الواحد نفسه.

        R-W2-006: أسطر الشيفرة/التعليق/الفراغ من تصنيف الماسح التدفقي
        (إحصاءة واحدة أثناء المسح — الكبير بلا تحميل كامل)، لا قراءة ثانية.
        الملفات غير المصنّفة (فشل قراءة) تُتخطى كما في القديم.
        """
        total_files = 0
        total_lines = 0
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        largest_files = []
        
        for entry in self._shared.files:
            if entry.is_dir:
                continue
            total_files += 1
            if entry.metric_lines < 0:
                continue

            total_lines += entry.metric_lines
            comment_lines += max(entry.comment_lines, 0)
            blank_lines += max(entry.blank_lines, 0)
            largest_files.append((entry.path, entry.metric_lines))
        
        code_lines = max(total_lines - comment_lines - blank_lines, 0)
        
        # Get top 10 largest files
        largest_files.sort(key=lambda x: x[1], reverse=True)
        
        self.genome.metrics = RepositoryMetrics(
            total_files=total_files,
            total_lines=total_lines,
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            languages=self.genome.metrics.languages,
            language_lines=self.genome.metrics.language_lines,  # R-W2-003
            largest_files=largest_files[:10],
            depth=self.genome.metrics.depth
        )
