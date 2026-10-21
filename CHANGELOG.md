# سجل التغييرات — AGOS

> كل مدخل مرتبط ببند في [ROADMAP.md](ROADMAP.md) وسجل عمل في `docs/worklog/` (GOVERNANCE G1).
> الصيغة مبنية على [Keep a Changelog](https://keepachangelog.com/).

## [غير مُصدَر]

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
