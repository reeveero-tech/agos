# سجل التغييرات — AGOS

> كل مدخل مرتبط ببند في [ROADMAP.md](ROADMAP.md) وسجل عمل في `docs/worklog/` (GOVERNANCE G1).
> الصيغة مبنية على [Keep a Changelog](https://keepachangelog.com/).

## [غير مُصدَر]

### 0018 — استخراج الاعتماديات من ملفات الاعتماديات، مطابقاً لمستودعات مرجعية — 2026-10-21 — R-W2-002
#### أُصلح
- **`dependencies` كانت فارغة دائماً** في DNA المسار الحي (`dependencies=[]`) وفي rie. صارت تحمل الاعتماديات المباشرة (runtime وpeer).
- **ستة مستخرجين معطوبين:**
  - civilization `DependencyAnalyzer`: محللات pyproject وPipfile وCargo وMaven وGradle تعيد `[]`، وgo.mod يأخذ كل سطر، و`-r` و`--index-url` تُعدّ حزماً، والبحث ينزل إلى `node_modules`؛
  - `DependencyResolutionStage`: الجذر فقط وبأسطر خام؛
  - شريحة repo_discovery: تنزل إلى `node_modules`؛
  - intelligence: الجذر فقط، وكل pyproject يعني poetry؛
  - مديرو الحزم بالمطابقة الجزئية: Gradle يعني "maven"، وcomposer وpub غائبان.
#### أُضيف
- **في `stack_detection`:**
  - `Dependency.specifier` (قيد الإصدار كما كُتب، في كل الصيغ)؛
  - صيغة `*.gemspec`؛
  - `project_dependencies` و`dependency_records`؛
  - `detect_package_managers` و`detect_package_managers_at` (من ملفات الاعتماديات والقفل)؛
  - النطاقات `build` و`local` و`parent` و`plugin`؛
  - `FRAMEWORK_SCOPES`.
- **حقل `dependency_details`:** في `RepositoryDNA` في النواة، و`RepositoryDNA` و`RepositoryFeatureSet` في rie، و`RepositoryGenome`، ودائماً آخراً وفي `to_dict()`.
- **حقول أخرى:** `RepositoryGenome.dependencies`، و`DependencyGraph.other_dependencies`، و`_detect_dependencies` في `RepositoryAnalyzer`.
- **`tests/test_dependency_extraction.py`** (59 اختباراً): 15 مستودعاً مرجعياً محلياً، و7 مستودعات حقيقية مثبتة بالوسوم، و14 كناري قيود، و11 كناري نطاقات، و7 مسارات من طرف إلى طرف.
#### تغيّر
- **المسارات السبعة صارت واجهات لمصدر واحد:** القدرة الحية، وrie، وDependencyAnalyzer، وDependencyResolutionStage مع pipeline، وRepositoryAnalyzer مع ProjectDNA، والشريحة.
- **`_generate_dna`** يقبل `stack` اختيارياً.
- **مديرو الحزم:** gradle بدل maven، وملفات القفل تضيف yarn وpnpm وuv وbun وغيرها.
- **الدوال والجداول القديمة محفوظة** مرجعاً غير مستعمل (لا حذف): `DEPENDENCY_FILES` و`dependency_files` و`_detect_package_managers_by_root_files`.
#### النتيجة
- **الاختبارات:** 375 / 0 / 0 / 0. التحذيرات 38، وكلها R-Q-001.
- **المستودعات المرجعية:** 22 من 22 مطابقة، ومنها `psf/requests@v2.32.3` ← 4، و`pallets/flask@3.0.3` ← 6، و`gin@v1.9.1` ← 12، و`sinatra@v4.0.0` ← 8، و`ripgrep@14.1.0` ← 21، و`express@4.19.2` ← 31.
- **أدوات التدقيق:** فشل الاستيراد 0 / 522، والبيئة النظيفة 491 / 491، ومشاكل التبعيات 0.

### 0017 — كشف الأطر من ملفات الاعتماديات بالأدلة، وتوحيد الكواشف الستة — 2026-10-21 — R-W2-001
#### أُصلح
- **الإيجابيات الكاذبة في كشف الأطر** (التدقيق §3.6). ذِكر اسم إطار في README أو توثيق أو نص شيفرة أو اسم ملف (`app.py` و`manage.py` و`settings.py` و`config.ru` و`pages/`) لم يعد دليلاً. `psf/requests` كان ينتج `Express, Flask, Next.js, Vue`، وصار `[]`.
- **سلك ميت في rie:** `DetectorContext.get_file_content` كان يقرأ `metadata["_content"]`، والمطبِّع لا يملؤه أبداً. صار يحمل محتوى ملفات الاعتماديات فقط.
- **ستة كواشف متعارضة** كان كلٌّ منها يقرر «ما الأطر؟» بقاعدته: القدرة الحية، وrie، وcivilization، وintelligence، وtechnology، وrepo_discovery. صارت كلها واجهات لقاعدة واحدة.
#### أُضيف
- **الوحدة `agos/agos-kernel/stack_detection/`** (`agos.kernel.stack_detection`). تعتمد على المكتبة القياسية فقط، وتحلل 13 صيغة ملف اعتماديات:
  - requirements* وpyproject (PEP 621 وPoetry وPDM وdependency-groups) وsetup.cfg؛
  - setup.py عبر AST دون تنفيذ؛
  - Pipfile وpackage.json وGemfile وcomposer.json وpom.xml وGradle وgo.mod وCargo.toml وpubspec.yaml.
- **قواعد الوحدة:**
  - مطابقة تامة للأسماء؛
  - نطاقات (`runtime`/`peer` تُحتسب؛ `dev`/`optional`/`build`/`indirect`/`example` أدلة فقط)؛
  - تخطي المجلدات المُورَّدة؛
  - تسجيل الملفات المشوهة في `errors`.
- **حقلان في `RepositoryDNA`:** `framework_evidence` و`runtimes`، في آخر الصنف وفي `to_dict()`. وأُضيف `framework_evidence` إلى مخرجات الكواشف الأخرى.
- **`tests/test_framework_detection.py`** (61 اختباراً): الذهبيان A وB على الوحدة وعلى المسارات الستة، و21 كناري صيغ، و16 كناري نطاقات، واختبار شبكي على `psf/requests`.
- **`stack_detection`** في `tools/audit/module_map.py`.
#### تغيّر
- `features["frameworks"]` في rie صارت أطراً حقيقية، وانتقلت بيئات التشغيل إلى `features["runtimes"]`.
- المسار الحي لم يعد يضع Python أو Node.js في `frameworks`.
- `TechnologyDetectionCapability.execute` يقبل `contents`، وبلا محتوى لا يدّعي أي إطار.
- الجداول والدوال النصية القديمة **محفوظة** مرجعاً غير مستعمل (لا حذف): `_detect_frameworks_by_text` (×2)، و`LEGACY_FRAMEWORK_MARKERS`، و`FRAMEWORK_PATTERNS`.
#### النتيجة
- **الاختبارات:** 316 / 0 / 0 / 0. التحذيرات 38، وكلها R-Q-001.
- **الجرد وسجل الوحدات:** فشل الاستيراد 0 / 522. المستويات 0 / 112 / 8 / 2 / 12. `unmapped = []`.
- **البيئات والتبعيات:** البيئة النظيفة 491 / 491، ومشاكل التبعيات 0.
- **القياس اليدوي:** أنتج `fastapi/full-stack-fastapi-template` ‏`FastAPI, React`، وأنتج `spring-projects/spring-petclinic` ‏`Spring`.

### 0016 — توقيت UTC واعٍ بالمنطقة بدل `datetime.utcnow()` — 2026-10-21 — R-F-012
**أُصلح**
- 265 استدعاءً لـ`datetime.utcnow` في 105 ملفات صارت `datetime.now(timezone.utc)`، وأُضيف `timezone` إلى استيراد `datetime` في كل ملف منها.
  - و`default_factory=datetime.utcnow` صار `default_factory=lambda: datetime.now(timezone.utc)`.
- **عيب حقيقي:** `.timestamp()` على الوقت الساذج يفسّره بالتوقيت **المحلي**. فعلى مضيف بتوقيت الرياض (UTC+3) كانت مدة كل span في `telemetry_runtime` تُحسب بثلاث ساعات زائدة، وكذلك كانت المعرّفات المبنية على الطابع الزمني في `fabric` و`seos` و`cloud`، وعددها 7.

**أُضيف**
- `tools/migrate/aware_utc.py`: أداة تحويل مبنية على AST. لا تلمس التعليقات والنصوص، وتحسب مواضع الأحرف بالبايت (UTF-8)، وتعالج الاستيراد داخل الدوال، ولا يتغير الملف إن أُعيد تشغيلها. و`--check` يفشل إن بقي موضع.
- `pyproject.toml`: `filterwarnings = ["error:datetime.datetime.utcnow:DeprecationWarning"]`، فأي عودة لـ`utcnow` تُفشل المجموعة.
- `tests/test_aware_utc.py`: 5 اختبارات:
  - لا موضع متبقٍّ؛
  - الحارس مفعّل؛
  - كناري الأداة بكل الأشكال؛
  - مدة span صحيحة تحت `TZ=Asia/Riyadh`، مع كناري يثبت أن الصيغة القديمة تخطئ بثلاث ساعات؛
  - الطوابع الزمنية تنتهي بـ`+00:00`.

**النتيجة:**
- `DeprecationWarning` في مجموعة الاختبارات: 0.
- التحذيرات الكلية: 2410 ← 38، والباقي `PytestReturnNotNoneWarning` ← R-Q-001.
- الاختبارات: 255 ناجحاً و0 فاشلة.
- **المسار F مكتمل (12/12).**

### 0015 — تدقيق التبعيات الخارجية وإثباتها في بيئة نظيفة — 2026-10-21 — R-F-011
**أُضيف**
- `tools/audit/dependencies.py`: يحلل AST لكل ملفات `agos/` و`tests/` و`tools/` (543 ملفاً) ويصنّف كل استيراد خارجي:
  - في كود المنصة (runtime)؛
  - في الاختبارات (dev)؛
  - في الأدوات (tooling)؛
  - اختياري، أي محمي بـ`try/except ImportError`؛
  - داخل قالب كود تولّده المنصة (generated).

  ثم يقارنها بـ`pyproject.toml` و`uv.lock`. يكتب `docs/audit/dependencies.{json,md}`، و`--check` يُفشل CI إن ظهرت مشكلة أو تقادم التقرير.
- `tools/audit/clean_env.py`: يبني بيئة جديدة فيها اعتماديات التشغيل المقفلة وحدها مع حزمة `agos`، بلا مجموعة dev. ثم يقلع النواة من الحزمة المثبتة، ويستورد كل وحدة تشغيل. يكتب `docs/audit/clean_env.json`، والخيار `--without=<dist>` وضع كناري.
- مهمة CI جديدة اسمها `clean-environment` تشغّل الأداتين مع `--check`.
- `tests/test_dependency_audit.py`: 6 اختبارات، منها كناريات التصنيف والكشف.

**تغيّر**
- `pyproject.toml`: صُحّح تعليق `requests`. فهو لا يُستورد في كود المنصة، بل يحتاجه كود عملاء SDK الذي تولّده المنصة. لم تتغير الاعتماديات ولا `uv.lock`.

**النتيجة:**
- 490 من 490 وحدة تشغيل تُستورد في البيئة النظيفة، والإقلاع ناجح، ولا يظهر `ModuleNotFoundError` لأي حزمة خارجية.
- تدقيق التبعيات: 0 مشاكل.
- الاختبارات: 250 ناجحاً، و0 فاشلة، و0 أخطاء، و0 متخطاة.

### 0014 — إغلاق الإخفاقات المكشوفة وفحوص أمنية بـAST — 2026-10-21 — R-Q-009
**أُصلح**
- أُزيل `exec(compile(...))` من 9 حزم مستعارة. صارت تحمّل الكود بـ`importlib.machinery.SourceFileLoader(...).exec_module(...)`. الحزم هي:
  - `event_engine` و`mission_engine` و`skill_engine` و`decision_pipeline` و`execution_context` و`resource_manager` و`state_store`؛
  - `agos-kernel/agos_kernel`؛
  - `tools/packaging/agos_kernel_installed.py`.
- `agos/agos_kernel/__init__.py`: الدالة `_read_literal_metadata()` تقرأ `__version__` و`__phase__` و`__doc__` بتحليل AST بدلاً من `exec`.

**أُضيف**
- `agos/agos-kernel/core/tests/security_scan.py`: فاحصات AST للكود الديناميكي، والأسرار الثابتة، وبناء SQL بالسلاسل، والاستيراد الديناميكي غير الآمن، والاستيرادات غير المعلنة.
- `tests/test_security_scanners.py`: 54 كناري تثبت أن الفاحصات تلتقط الأنماط الحقيقية ولا تخطئ في الإيجابيات الكاذبة المعروفة.
- `registry.build_manifest()` و`KernelRuntime.manifest()` و`tools/audit/registry_manifest.py` (فيه الخيار `--check`) والملف `registry/manifest.json`: بيان مُرقَّم وحتمي للسجلات.
- `tests/test_registry_manifest.py`: يتحقق أن البيان المُلتزَم يطابق إقلاعاً جديداً، فلا يمكن أن يتقادم.

**تغيّر**
- `test_golden_security.py` و`test_golden_compatibility.py`: الاختبارات بأسمائها نفسها، لكنها تستخدم الفاحصات الجديدة. اختبار التبعيات صار أشد: يفشل عند أي استيراد غير معلن، وكان يقبل حتى 5.

**النتيجة:** الاختبارات 244 ناجحاً و0 فاشلة. خط الأساس: 0 إخفاقات معروفة و0 مكشوفة.

### 0013 — خط الأساس بلا إخفاقات معروفة — 2026-10-21 — R-F-010
**أُضيف**
- `agos/agos-kernel/conftest.py`:
  - المثبّتان `platform` و`report`. يستدعيان دالة الإنتاج نفسها التي يستدعيها `main()` في `test_runtime` و`test_intelligence`، مرة واحدة لكل وحدة.
  - أي سطر يبدأ بـ`✗` في هاتين الوحدتين صار يُفشل الاختبار.
- `agos/agos-kernel/core/tests/conftest.py`: المثبّت `kernel_dir` مشتركاً بين الأصناف. كان معرّفاً داخل `TestKernelSecurity` وحده.
- `tests/test_kernel_conftest.py`: اختباران للخطافين.

**النتيجة:**
- 15 إخفاقاً معروفاً صارت 0، و`known_failures = []`.
- الاختبارات: 181 ناجحاً، و7 فاشلة (كلها `revealed` ← R-Q-009)، و0 أخطاء.
- بنود المسار F الحرجة (R-F-001..010) مكتملة. بقي R-F-011 وR-F-012.

### 0012 — سجل الوحدات يرى اختبارات tests/ — 2026-10-21 — R-Q-010
**أُضيف**
- `tools/audit/inventory.py`: الدالة `external_test_references()` والقسم `external_tests` في `inventory.json`. يُسجَّل في الملفات الحقل `tested_by_external`. تُقرأ الاستيرادات من ثلاثة مواضع: ملف الاختبار نفسه، وسلاسل الكود التي يشغّلها في مفسّر مستقل (ومنها f-strings)، وأسماء سكربتات النواة التي ينفّذها مثل `main.py`.
- `tests/test_audit_tools.py`: اختباران.

**تغيّر**
- `tools/audit/module_register.py`: عمود «مختبَر» يحتسب `tests/*.py`. لم تتغير مجاميع الجرد (521 ملفاً داخل `agos/`).

**النتيجة:** L4 صارت 12 بعد أن كانت 4، وL2 صارت 7 بعد أن كانت 15. صعدت إلى L4 الحزم: `bootstrapper`، و`agos_runtime`، و`discovery`، و`registry`، و`resolvers`، و`interfaces`، و`shared`، و`mission_engine`.

### 0011 — واجهة النواة AGOSKernel — 2026-10-21 — R-F-008
**أُضيف**
- `agos/agos-kernel/core/kernel.py`:
  - `AGOSKernel`: الدورة `start`/`shutdown`، ومدير السياق، و`health()`، والسجلات.
  - `MissionManager`: يزامن كائن `Mission` مع النتيجة.
  - `MissionResult`، و`KernelState`، و`KernelNotRunning`.
  - يُصدَّر كل ذلك كسولاً من `core`، ويقوم فوق `agos_runtime.boot()`.
- `agos/agos-kernel/diagnostics/health.py`: الصنفان `KernelHealthService` و`KernelHealthReport`. يفحصان أربعة أشياء حقيقية: القدرات، والموفّرين، والعقود، وتغطية المهارات، ويستعملان أنواع `observability`.
- `agos/agos-kernel/conftest.py`: كل دالة في `test_validation` تُرجع `False` تُحسب فاشلة (لم يكن pytest يرى ذلك)، والدوال الشبكية تُتخطى بسبب صريح عند انقطاع الشبكة.
- `capabilities`: ذاكرة تحليل مفتاحها `(url, branch, commit)` عبر `git ls-remote`، لأن التحليل idempotent (المادة 14). ويمكن تعطيلها بـ`{"cache": False}`.
- `tests/test_kernel_facade.py`: 8 اختبارات.

**النتيجة:**
- `test_validation.py` يُجمع، وينجح 8/8 فعلياً تحت pytest وتحت `main()`. يشمل ذلك 100 مهمة متتالية على OpenHands في نحو 43 ثانية.
- **أعطال الاستيراد 0 من 521 لأول مرة.**
- الحزم في L0 صارت 0.
- الاختبارات 146 ← 162 ناجحاً.
- خط الأساس تقدّم إلى 15 فشلاً معروفاً.

### 0010 — مسار الإقلاع الوحيد — 2026-10-21 — R-W3-001
**أُضيف**
- `agos/agos-kernel/agos_runtime/__init__.py`: نقطة الدخول `boot()`، وتعيد مقبض `KernelRuntime` يحمل السجلات وناقل الأحداث ومحرك المهام ومحرك العقود، وفيه `run()` و`analyze()` و`summary()` و`require_ready()`.
- `discovery`: `kernel_root()`، واكتشاف كل `ICapability` و`IProvider` في جذر الحزمتين بلا `reload`.
- `bootstrapper`: التحقق من العقود عبر `ContractEngine`، و`EventBus` حقيقي، وتحذيرات صريحة للمكوّنات غير المحمّلة.
- `tests/test_bootstrap.py`: 10 اختبارات (إقلاع، هوية أصناف، مهمة من طرف إلى طرف بأحداثها، فشل صريح، فريدية المعرّف، المحلّل، مساحة الأسماء، `main.py`).
- بند جديد في الخارطة: R-Q-010.

**أُصلح**
- كان `Bootstrapper` و`AutoDiscovery` يبحثان في مجلديهما بدل جذر النواة، فيفشل كل إقلاع افتراضي برسالة «No capabilities loaded».
- كان خط التنفيذ يُعطى `event_bus=None`، فتنهار أول مهمة.
- كان `ProviderResolver.supported_skills` يُحسب من متغير الحلقة لا من الموفّر المختار.
- كانت المهمة المبنية من قاموس بلا `id` تحمل معرّفاً فارغاً.

**تغيّر**
- `main.py` و`agos-analyze` يقلعان عبر `agos_runtime.boot()` ويشغّلان التحليل مهمةً عبر محرك المهام، مع الحفاظ على صيغة المخرجات وأكواد الخروج.

**النتيجة:** الإقلاع ينجح (قدرة واحدة وموفّر واحد بعقود صالحة)، والاختبارات 136 ← 146 ناجحاً.

### 0009 — تصفير أعطال الاستيراد — 2026-10-21 — R-F-007
**أُضيف**
- `agos/agos-kernel/diagnostics/runtime.py`: الوحدة التي يستوردها `diagnostics/__init__.py` ولم تُلتزم قط؛ تعيد تصدير `SelfDiagnosticsRuntime` و`DiagnosticReport` من `crossdomain/runtime.py`، فالتنفيذ واحد والعنوانان صالحان.
- `tests/test_import_health.py`: 3 اختبارات (استيراد `diagnostics` مع وحدة الهوية، استيراد `decision`، و`Result` العام مع التوافق الخلفي).

**تغيّر**
- `agos/agos-kernel/shared/__init__.py`: صار `Result` عاماً (`Generic[T]`)، فأصبح `Result[Decision]` في `decision` صالحاً. السلوك وقت التشغيل لم يتغير.

**النتيجة:** أعطال الاستيراد 3 ← 1 (الباقي `test_validation` وهو نطاق R-F-008)، والاختبارات 133 ← 136 ناجحاً، وحزم L0 3 ← 1.

### 0008 — الاختبارات غير المتزامنة — 2026-10-21 — R-F-009
**تغيّر**
- `pyproject.toml`: `pytest-asyncio>=0.24` في مجموعة `dev`؛ `asyncio_mode = "auto"`.
- `uv.lock`: أُضيف `pytest-asyncio 1.4.0` (+ `typing-extensions`).
- `docs/quality/test_baseline.json`: تقدّم المراقب (21 ← 16 معروفاً).

**النتيجة:** اختبارات `test_execution_implementation` الخمسة (محرك التنفيذ، المهارات، الموفّرون، المحوّلات، التكامل) تعمل وتنجح؛ الاختبارات 128 ← 133 ناجحاً.

### 0007 — تغليف حقيقي — 2026-10-21 — R-F-001
**تغيّر**
- `pyproject.toml`: من قالب Replit (`repl-nix-workspace`، بلا نظام بناء) إلى الحزمة `agos 0.1.0.dev0` — `hatchling`، التبعيات الفعلية الأربع موثقة بمواضع استخدامها، `pytest` في مجموعة `dev`، `testpaths`، أمر `agos-analyze`.
- `uv.lock`: أُعيد توليده للحزمة `agos`.
- `agos/agos_kernel/__init__.py`: `_find_kernel_dir()` — يجد النواة في الشجرة المصدرية أو في الحزمة المثبتة.
- `README.md`: التثبيت والتشغيل.

**أُضيف**
- `agos/cli.py`: أمر `agos-analyze` (يغلّف `agos.kernel.main`).
- `tools/packaging/agos_kernel_installed.py`: `agos_kernel` العلوي في العجلة (ينفّذ التنفيذ الوحيد).
- `tests/test_packaging.py`: البيانات الوصفية، **كل استيراد خارجي معلن**، وهدف أمر الطرفية.

**النتيجة:** `uv sync` و`uv build` ينجحان؛ العجلة المثبتة في بيئة نظيفة خارج المستودع تعمل (`agos`, `agos.kernel`, `agos_kernel` بهوية واحدة بأي ترتيب، `rie`، `agos-analyze`).

### 0006 — إحياء rie — 2026-10-21 — R-F-006
**أُضيف**
- `agos/rie/__init__.py`: `rie` حزمة عادية موثقة (كانت حزمة namespace ضمنية).
- `tests/test_rie_pipeline.py`: اختبار طرف-لطرف على مستودع git محلي حقيقي.

**تغيّر**
- 8 ملفات في `rie` (12 استيراداً): استيرادات نسبية بدل `from contracts`/`from domain`/`from application`/`from rie.X` — كانت تلتقط `contracts` النواة و`domain` المنصة بالخطأ.
- `tests/test_namespace_identity.py`: `KNOWN_NAMESPACE_FAILURES` أصبحت فارغة.

**النتيجة:** خط RIE (fetch ← normalize ← detect ← aggregate ← DNA) يعمل لأول مرة؛ 138/138 وحدة منصة تحت `agos.*`؛ أعطال الاستيراد 8 ← 3.

### 0005 — مساحة الاسم الموحدة agos.* — 2026-10-21 — R-F-005
**أُضيف**
- `agos/__init__.py`: الحزمة `agos` — كل حزمة منصة كـ `agos.<name>`، والنواة كـ `agos.kernel` (نفس كائنات `agos_kernel`)، مع هوية وحدة واحدة في كل الاتجاهات (`agos.X` ⇄ `X` المجرد لغير المتصادمة)، و`platform_packages()`.
- `agos/ecosystem/global_ecosystem.py`: اسم قابل للاستيراد لـ `ecosystem/global.py` (`global` كلمة محجوزة) — نفس الكائن.
- `tests/test_namespace_identity.py`: 19 اختباراً لضمانات الهوية والترتيب والتصادم (R-F-003/004/005)، منها اختبار قبول R-F-005 مع قائمة أعطال معروفة لا تتسع.
- مدخل `__init__.py` في `tools/audit/module_map.py`.

**تغيّر**
- `cloud/integration.py`, `seos/execution/__init__.py`: استيرادات نسبية.
- 5 وحدات مكتبية في النواة (`core/autonomous`, `v2/runtime`, `brain/engine`, `civilization/runtime`, `platform_runtime/runtime`): `sys.path.insert(0, kernel)` ← إلحاق مشروط مرة واحدة (كان يحجب حزم المنصة المتسمّية بنفس الاسم).
- 7 ملفات نواة (21 استيراداً): استيراد الأسماء المتصادمة التسعة عبر `agos_kernel.X` بدل الاسم المجرد.

**النتيجة:** 132/137 وحدة منصة تُستورد كـ `agos.<name>` مع النواة في عملية واحدة (الباقي `rie` ← R-F-006)؛ 58/58 وحدة `agos_kernel` تعمل من `agos/` ومن `agos-kernel/`؛ الاختبارات 105 ← 124 ناجحاً؛ `main.py` يعمل.

### 0004 — أسماء قابلة للاستيراد للمجلدات ذات الشرطة — 2026-10-21 — R-F-004
**أُضيف**
- 7 حزم بديلة في `agos/agos-kernel/`: `event_engine`, `mission_engine`, `skill_engine`, `decision_pipeline`, `execution_context`, `resource_manager`, `state_store` — كل منها يوجّه `__path__` إلى المجلد الأصلي وينفّذ شيفرته (المجلد الأصلي مصدر الحقيقة، لم يُنقل ولم يُسمَّ).
- `tools/audit/inventory.py`: `alias_module_name()` — فحص الملفات ذات الشرطة عبر اسمها البديل.
- `tools/audit/module_map.py`: الحزم البديلة ترث مدخل المجلد الأصلي.

**أُصلح (أخطاء كامنة ظهرت بالإحياء)**
- `skill-engine/__init__.py`: `SkillResult.started_at` حقل بلا قيمة افتراضية بعد حقول افتراضية ← `TypeError` عند تعريف الصنف؛ أُعطي `default_factory=datetime.utcnow` (كل الاستدعاءات بالاسم).
- `hardening/runtime.py`: `Tuple` مستخدم قبل استيراده المتأخر ← أُضيف إلى استيراد `typing` العلوي.

**النتيجة:** `bootstrapper` و`hardening.runtime` يُستوردان؛ أعطال الاستيراد 17 ← 8؛ L0 13 ← 4.

### 0003 — الاسم المستعار agos_kernel — 2026-10-21 — R-F-003
**أُضيف**
- `agos/agos_kernel/__init__.py`: حزمة `agos_kernel` مع مستورد مسار (meta-path finder) يجعل `agos_kernel.X` **نفس كائن** الوحدة `X` في النواة؛ ويعيد تصدير `__version__`/`__phase__` للنواة؛ لا يحجب الأسماء المتصادمة التسعة.
- `agos/agos-kernel/agos_kernel/__init__.py`: حزمة تمرير تنفّذ التنفيذ الوحيد أعلاه (حين يكون `agos-kernel` على المسار).
- مدخلان في `tools/audit/module_map.py`.

**أُصلح**
- `civilization/knowledge_graph/builder.py`: استيراد `KnowledgeGraph` الناقص (خطأ كامن ظهر بمجرد إحياء الحزمة) — إضافة سطر استيراد.

**النتيجة:** 51/51 وحدة تستورد `agos_kernel` تعمل (من `agos/` ومن `agos-kernel/`)؛ أعطال الاستيراد 107 ← 17؛ الاختبارات 105 ناجحاً (+2 أُصلحا).

### 0002 — مسارات محمولة — 2026-10-21 — R-F-002
**تغيّر**
- 60 ملفاً في `agos/`: استُبدلت المواضع الـ126 للمسار الثابت `/home/runner/workspace/agos` بقيم محسوبة من موقع الملف (`_AGOS_ROOT`, `_AGOS_KERNEL`) قابلة للتجاوز بمتغير البيئة `AGOS_ROOT`. لم تُحذف أي دالة أو منطق.
- `tools/quality/run_tests.py`: دعم قسم `revealed` في خط الأساس (إخفاقات كشفها إصلاح اختبار كان فارغاً، كلٌّ بسببه وبنده).
- `tools/audit/inventory.py`: إخفاء مسار البيئة المحلية من المخرجات (`<repo>`).
- `tools/governance/check_commit.py`: استثناء التاريخ السابق للحوكمة (`GENESIS = b9ca3e9`) في وضع `--range`.

**أُضيف**
- `tools/migrate/portable_paths.py`: أداة إعادة كتابة آمنة على مستوى الرموز (tokenize) وقابلة للتكرار، مع `--check`.
- البند `R-Q-009` في الخارطة.

**النتيجة:** المسارات الثابتة 126 ← 0؛ الاختبارات 81 ← 103 ناجحاً، المتخطاة 18 ← 0؛ 11 إخفاقاً قديماً أُصلح، و7 إخفاقات حقيقية كُشفت (R-Q-009).

### 0001 — الحوكمة وخارطة الطريق — 2026-10-21 — R-G-001..R-G-005, R-G-007, R-W1-001
**أُضيف**
- `GOVERNANCE.md`: القاعدة G1 (الدفعة الموثقة الذرية) والقاعدة G2 (منع الحذف).
- `ROADMAP.md`: خارطة شاملة (المسارات G, F, W1–W5, Q, D, REL) بـ 122 بنداً بمعايير قبول.
- `PROJECT_STATE.md`، `CHANGELOG.md`، `AGENTS.md`، `README.md` جذري، `.gitignore` جذري.
- `tools/governance/check_commit.py` + `.githooks/` (pre-commit, commit-msg, pre-push) + `tools/governance/install_hooks.sh`.
- `.github/workflows/governance.yml`: بوابة الحوكمة لكل التزام + الاختبارات.
- `tools/audit/inventory.py`، `tools/audit/module_map.py`، `tools/audit/module_register.py`.
- `tools/quality/run_tests.py` + خط الأساس `docs/quality/test_baseline.json` (34 فشلاً معروفاً).
- `docs/audit/AUDIT-2026-10-21.md` (الدراسة الشاملة)، `docs/audit/inventory.{md,json}`.
- `docs/architecture/ARCHITECTURE.md`، `MODULE_REGISTER.md`، `DEPRECATIONS.md`.
- ADR-0001 (مساحة الأسماء)، ADR-0002 (منع الحذف والإيقاف المنظم)، ADR-0003 (مستويات الحياة).

**تغيّر**
- `agos/push_to_github.sh`: تعليم كمتقادم + حارس يمنع تشغيله عرضاً (لم يُحذف).
- `replit.md`: تعليم كمتقادم في رأس الملف (لم يُحذف).

**الكود الوظيفي:** لم يتغير أي سطر في وحدات `agos/` في هذا الالتزام.
