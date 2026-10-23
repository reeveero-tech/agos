# ADR-0012: توحيد الإدراك (R-W1-010)

**الحالة:** معتمد — قرار معماري وثائقي؛ الترحيل التشغيلي **غير منفذ** (الأعمال المسماة أدناه)
**التاريخ:** 2026-10-23
**البند:** R-W1-010 — توحيد الإدراك (`cognitive`, `cognition`) — مخرج
الخارطة: ADR

## السياق

سطحان باسمين متقاربين يعلنان مسؤوليات إدراكية متداخلة (نية، فهم،
استنتاج، تخطيط، تقييم، تحقق، قرار) بلا مسار واحد:

- `agos/cognitive/` — 11 ملفاً، 606 أسطراً، نسخ 1.0.0، سلسلة
  EXECUTION-000021..30.
- `agos/cognition/` — 6 ملفات، 367 سطراً، نسخ 10.0.0 («Absolute
  Foundation»، «World Model»، «Cognitive Core»).

مسح كامل (تنفيذ، مدخلات، مستهلكون، اختبارات) بالبحث المؤهل والعاري
والنسبي وبحث الرموز لقائمة الواجهات الرئيسية للسطحين خارج تعريفاتها.

**المستهلكون (في البحث المحدد)**:

- **لم يظهر مستهلك إنتاجي في البحث المحدد**. شمل البحث قائمة محددة من
  الواجهات الرئيسية — UniversalCognitiveCore، UniversalWorldModel،
  AbsoluteFoundation، UniversalSkillFabric، UniversalCompositionEngine،
  UniversalDecisionPlatform، UniversalDeliberationEngine،
  UniversalPlanningEngine، UniversalConstraintPlatform،
  UniversalGoalPlatform، UniversalContextEngine، UniversalIntentEngine،
  UniversalReasoningRuntime، UniversalEvaluationPlatform،
  UniversalStrategyPlatform، WorldGraph، RelationshipEngine،
  SkillComposer — ولم يجد استعمالاً خارج تعريفاتها إلا واحداً: `tests/test_decision_unification.py:352-353` يستورد
  `UniversalDecisionPlatform` (سطح cognitive/decision) باختبار سلوكي
  فعلي (تأكيدات على الوسم والمختار والمرفوض).
- `agos/agos-kernel/decision-pipeline/{__init__,explain}.py` يذكران
  `cognitive.decision` في docstrings بوصفه مسار تسجيل caller-provided —
  بلا استيراد.
- `agos/agos-kernel/civilization/engineering_brain/brain.py` يعرّف
  `EngineeringCognitionRuntime` محلياً (تشابه اسم لا صلة بالسطحين —
  `agos/agos-kernel/civilization/engineering_brain/brain.py::EngineeringCognitionRuntime`).

**التغطية الاختبارية (في البحث المحدد)**: ظهر اختبار سلوكي لتسجيل
القرار — `tests/test_decision_unification.py:350-363` لـ`cognitive.decision`
(تأكيدات فعلية: `evidence_provenance == "caller-provided"` والمختار
والمرفوض)؛ ولم يظهر اختبار سلوكي لبقية الواجهات الرئيسية المشمولة
بالبحث. و`tests/test_namespace_identity.py:82`
يفحص هوية النطاقات (bare/qualified) لا السلوك.

## مصفوفة الأدلة (بأرقام أسطر مثبتة بالاستخراج، وإعادة إنتاج منفذة للعيوب)

| السطح | المسؤولية المعلنة | الآلية الفعلية (وصف تشغيلي) | الأدلة |
|---|---|---|---|
| `agos/cognitive/decision.py` | «Universal Decision Platform» | **واجهة تسجيل صادقة (R-W1-004/ADR-0006)**: `Decision.evidence_provenance="caller-provided"` (28)؛ `make_decision` (71-79) يسجل المختار ويشتق المرفوض من البدائل؛ `DecisionRegistry.register/get` تخزين منفذ؛ والإحصاءات من السجل الفعلي. **حد مسمى**: التسجيل لا يقيّم؛ ووصف الصنف ما زال يعد بواجهات غير منفذة (Graph/Simulator/Optimizer/History/Replay) — وعود غير مثبتة تميز عن التسجيل المنفذ | تسجيل منفذ بوسم مصدر — لا تقييم |
| `agos/cognitive/intent.py` | «Universal Intent Engine» | `IntentParser.parse` (19-20) يرجع Intent بمعرّف ثابت `"parsed"` وبوصف مرسل حرفياً — **لا فصل للنية** (لا أهداف ولا قيود تُستخرج)؛ `agos/cognitive/intent.py::IntentRegistry.register` منفذ لكن **إعادة الإنتاج أثبتت**: نيتان متتاليتان تحملان المعرّف نفسه ⇒ الثانية تستبدل الأولى والإحصاء total=1 — السجل لا يحفظ نوايا مستقلة | تسجيل منفذ بحد المعرّف الثابت — لا فصل نية ولا تاريخ مستقل |
| `agos/cognitive/context.py` | «Universal Context Engine» | `agos/cognitive/context.py::ContextRegistry.register/get` تخزين منفذ؛ `ContextComposer.compose` (30) يرجع صدى بنية (`{"composed": True, "sources": sources}`) — لا تركيب محتوى | تخزين منفذ؛ «تركيب» صدى هيكلي |
| `agos/cognitive/goal.py` | «Universal Goal Platform» | `agos/cognitive/goal.py::GoalRegistry.register/get` منفذ؛ `GoalHierarchy.build` (27) يرجع `{"children": []}` ثابتاً | تسجيل منفذ؛ «تسلسل» غير موصل |
| `agos/cognitive/planning.py` | «Universal Planning Engine» | `PlanValidator.validate` (14-15) **منفذ فعلاً**: يفحص عدم فراغ الخطوات (أثبت الاستدعاء: فارغة ⇒ False، بخطوة ⇒ True) — فحص شكلي لا تخطيطاً؛ و`create_plan` **منفذ فعلاً**: ينشئ `MissionPlan` بخطوة واحدة تجمع intent/goals/constraints كما وردت (ليس توليد خطة تنفيذية ولا تخزيناً في سجل)؛ `PlanSimulator.simulate` (19) يرجع `{"simulated": True, "outcome": "success"}` ثابتاً | فحص فراغ وإنشاء كائن منفذان؛ «محاكاة» نتيجة ثابتة |
| `agos/cognitive/constraint.py` | «Universal Constraint Platform» | `ConstraintSolver.solve` (17) يرجع `{"solved": True}` ثابتاً؛ `ConstraintValidator.validate` (21) يرجع True ثابتاً | «حل قيود» و«تحقق» بلا فحص |
| `agos/cognitive/reasoning.py` | «Universal Reasoning Runtime» | المستنتجات الثلاثة ترجع نصوصاً ثابتة (`"deduced_conclusion"` :8، `"induced_hypothesis"` :12، `"abduced_explanation"` :16) و`reason` (45) يرجع `"reasoned"` للمجهول | «استنتاج» نصوص ثابتة |
| `agos/cognitive/evaluation.py` | «Universal Evaluation Platform» | `EvaluationEngine.evaluate` (10) يرجع 0.8 لكل مقياس ثابتاً | «تقييم» قيمة ثابتة |
| `agos/cognitive/strategy.py` | «Universal Strategy Platform» | `StrategySelector.select` (8) يرجع صدى النوع مع `"selected": True` | «اختيار استراتيجية» صدى |
| `agos/cognitive/deliberation.py` | «Universal Deliberation Engine» | `AlternativeGenerator.generate` (18) يرجع بدائل ثابتة `["alternative_1","alternative_2"]`؛ `deliberate` (61-69) يضع `status="completed"` (69) بلا مداولة — والناقد والمحلل صدى فارغ | «مداولة» بلا مداولة |
| `agos/cognition/core.py` | «Universal Cognitive Core» | `think` (63-80) يسلسل مكالمات كلها ثابتة: تقييم `{"score": 100, "approved": True}` (29) وتحقق `{"verified": True}` (33) وقرار = **البديل الأول حصراً** (37) — **منفذ فعلاً**: اختيار أول بديل سياسة ترتيب بسيطة منفذة، ليست تقييماً مثبتاً لجودة البدائل | تسلسل منفذ فوق نتائج ثابتة؛ القرار ترتيب لا تقييم |
| `agos/cognition/foundation.py` | «Absolute Foundation» | `VerificationEngine.verify` (21) يرجع True ثابتاً؛ `verify_all` (62-63) يرجع True لكل المكونات التسعة عشر بلا فحص؛ `release` (65+) يدعي `architecture_locked/kernel_locked/contracts_locked: True` | «تحقق مؤسسة» و«قفل معماري» بلا فحص |
| `agos/cognition/model.py` | «Universal World Model» | `WorldGraph.add_entity/add_edge/get_entity` تخزين منفذ؛ `StateEngine.get_state` (29) يرجع `"active"` ثابتاً؛ `PredictionEngine.predict` (37) يرجع `"stable"`/0.9 ثابتين؛ **وعيب مثبت في المسار العام**: `agos/cognition/model.py::RelationshipEngine.find_relationships` يقرأ `self._edges` والسمة غير معرفة في الصنف — **أعيد إنتاجه بالاستدعاء العام** (`UniversalWorldModel().relationships.find_relationships(...)` ⇒ AttributeError) | تخزين منفذ؛ حالة/تنبؤ ثابتان؛ وعيب مسار عام معاد إنتاجه |
| `agos/cognition/composition.py` | «Universal Composition Engine» | `CompositionRuntime.create` تخزين منفذ؛ `CompositionValidator.validate` (22) True ثابت؛ `CompositionCompiler.compile` يرجع اسماً مركباً؛ `CompositionSimulator.simulate` (30) يرجع `"success"` ثابتاً | تخزين منفذ؛ «تحقق/محاكاة» ثابتان |
| `agos/cognition/skill.py` | «Universal Skill Fabric» | `SkillRegistry.register/get/search` منفذ (بحث بالاسم فعلي)؛ **وفجوة توصيل مثبتة**: `UniversalSkillFabric` ينشئ سجلين مستقلين (`registry` و`SkillComposer._registry`) — **أعيد إنتاجه بالفحص**: `fabric.registry is fabric.composer._registry` ⇒ False، و`compose([skill_id])` لمهارة مسجلة عبر الواجهة العامة يرجع [] — التسجيل العام لا يصل إلى التركيب؛ و`SkillBenchmark.benchmark` (38) يرجع 100ms/0.01 ثابتين | سجل مهارات منفذ **غير موصل بالتركيب**؛ «قياس أداء» ثابت |

## خريطة توحيد الواجهات الرئيسية (لكل مدخل عام: المسؤولية الباقية وحدودها، جهة التفويض أو التأجيل المبرر، وضع الواجهة أثناء الترحيل وفق G2 ومعيار قبول التوصيل)

| المدخل العام | المسؤولية الباقية المقترحة وحدودها | جهة التفويض / التأجيل المبرر | وضع الواجهة أثناء الترحيل (G2) ومعيار القبول |
|---|---|---|---|
| `cognitive.decision.UniversalDecisionPlatform` | **تسجيل قرارات خارجية بوسم مصدر** (مقيم المرسل، لا تقييم المحرك) — كما وصفها ADR-0006/R-W1-004 | معتمد أصلاً في ADR-0006: الاختيارات الحسابية من decision-pipeline، وهذا السجل caller-provided | الرموز والتواقيع تبقى (G2)؛ معيار القبول: إزالة الوعود غير المثبتة من وصف الصنف (Graph/Simulator/Optimizer...) أو تمييزها صراحة كغير منفذة، بلا تغيير سلوك التسجيل المثبت (اختبار 350-363 يبقى أخضر) |
| `cognitive.intent.UniversalIntentEngine` | **تسجيل نوايا معلنة من المرسل** — بحد مسمى: المحلل لا يفصل النية (معرّف ثابت ⇒ التسجيل الثاني يستبدل الأول؛ لا تاريخ نوايا مستقلاً) | **تأجيل فصل النية**: مرجع لآلية تفسير نية محدودة وفق العقد المعلن في مقدمة `agos/agos-kernel/intelligence/intent.py` (R-W1-006، سجل العمل 0047 — «آلية محدودة معلنة لا مفسر قصد حر»)؛ التفويض إليها يحتاج توافق عقد لا تشابه اسم | الرموز تبقى؛ معيار القبول: إما معرّفات مميزة تُثبت بتسجيل نيتين (total=2) أو تسمية الحد صراحة؛ ولا يُدَّعى فصل نية هنا |
| `cognitive.{context,goal}.Universal*` | **سجلات سياقات وأهداف معلنة** (تخزين/استرجاع منفذ) — بلا ادعاء تركيب سياق أو تسلسل أهداف | **تأجيل**: لم يظهر مستهلك إنتاجي في البحث المحدد — يوحَّد عند ظهور استعمال فعلي | الرموز تبقى؛ معيار القبول: إزالة الصدى الهيكلي (composer/hierarchy) أو تعليل غيابه، مع بقاء التسجيل |
| `cognitive.planning.UniversalPlanningEngine` | **فحص عدم فراغ الخطة منفذ** (validate) وإنشاء كائن خطة بخطوة واحدة من مدخلات المرسل — بلا ادعاء توليد تخطيط أو محاكاة | **تأجيل التوليد**: لا منفذ للتخطيط الدلالي في السطحين ولا مستهلك في البحث المحدد | الرموز تبقى؛ معيار القبول: simulate لا يدعي نجاحاً (نتيجة معللة عدم التنفيذ)؛ وvalidate يبقى بفحصه المنفذ |
| `cognitive.{constraint,reasoning,evaluation,strategy,deliberation}.Universal*` | لا مسؤولية إدراكية تُسند الآن: حل القيود والاستنتاج والتقييم والاستراتيجية والمداولة كلها نتائج ثابتة | **تأجيل**: لا منفذ لها في السطحين ولا مستهلك — تعيين أي مسؤولية يحتاج دليلاً وتوافق عقد | الرموز تبقى (G2)؛ معيار القبول: الادعاء الثابت يصبح معللاً بعدم التنفيذ أو يزال الادعاء، بلا حذف رموز |
| `cognition.core.UniversalCognitiveCore` | لا مسؤولية تُسند: تسلسل فوق نتائج ثابتة؛ قراره ترتيب أول بديل (سياسة بسيطة منفذة — ليست تقييماً) | **تأجيل**: لم يظهر مستهلك إنتاجي أو اختبار سلوكي في البحث المحدد | الرموز تبقى؛ معيار القبول: أي استعمال لاحق يوثق سياسة الترتيب صراحة ولا يدعي تقييماً |
| `cognition.foundation.AbsoluteFoundation` | لا مسؤولية: «تحقق» و«قفل» بلا فحص — ادعاءات تزال | **تأجيل** بنفس المبرر | الرموز تبقى؛ معيار القبول: verify/release لا يدعيان قفلاً أو تحققاً بلا فحص |
| `cognition.model.UniversalWorldModel` | **تخزين كيانات وحواف منفذ** (WorldGraph) — بلا ادعاء حالة أو تنبؤ؛ **والعيب المثبت**: find_relationships يعطل (AttributeError أعيد إنتاجه) | **تأجيل** بنفس المبرر | الرموز تبقى؛ معيار القبول: العيب يُصلح (قراءة الحواف من المصدر الفعلي) أو يعلل، والحالة/التنبؤ الثابتان يُصرّح بعدم تنفيذهما بمسوغ مسمّى |
| `cognition.{composition,skill}.Universal*` | **سجلات تركيبات منفذة** (تخزين) — و**سجل مهارات منفذ غير موصل بالتركيب** (فجوة مثبتة أعلاه) — بلا ادعاء تحقق تركيب أو قياس أداء | **تأجيل** بنفس المبرر | الرموز تبقى؛ معيار القبول: validate/benchmark لا يدعيان فحصاً أو قياساً؛ وفجوة التوصيل إما تصل (المهارة المسجلة تصل compose بنتيجة مثبتة) أو تعلل — والسجل والبحث يبقيان بنتائجهما |

## القرار المعماري (خريطة المسؤوليات)

1. **تسجيل القرارات**: `cognitive/decision.py` هو واجهة التسجيل الصادقة
   المعتمدة أصلاً في ADR-0006/R-W1-004 (وسم caller-provided، لا تقييم —
   نص ADR-0006: «واجهة تسجيل اختيارات خارجية — وسْم مصدر التقدير
   caller-provided (المحرك لا يقيّم)») — بحدوده المسماة، مع تمييز
   الوعود غير المثبتة في وصف صنفه عن التسجيل المنفذ.
2. **العمليات المنفذة تُحفظ بحدودها** (لا إزالة عمياء): سجلات القرارات
   والنوايا والسياقات والأهداف والمهارات والتركيبات والكيانات منفذة؛
   وفحص فراغ الخطة منفذ؛ واختيار أول بديل في DecisionEngine سياسة ترتيب
   بسيطة منفذة — توثق بوصفها ترتيباً لا تقييماً. حدودها موثقة: سجل
   النوايا لا يحفظ نوايا مستقلة (معرّف ثابت).
3. **الادعاءات الثابتة المحددة بالأدلة تُزال عند التنفيذ** (ليس استبدال كل
   True): حل القيود (constraint.py:17,21)، المداولة (deliberation.py:18,69)،
   التقييم (evaluation.py:10)، المحاكاة (planning.py:19)، الاستنتاجات
   النصية (reasoning.py:8,12,16,45)، الاستراتيجية (strategy.py:8)، تقييم
   وتحقق core (core.py:29,33)، «تحقق/قفل» المؤسسة (foundation.py:21,62,72)،
   الحالة/التنبؤ (model.py:29,37)، تحقق/محاكاة التركيب (composition.py:22,30)،
   وقياس المهارة (skill.py:38).
4. **عيوب وفجوات مسار عام معاد إنتاجها**: `RelationshipEngine.find_relationships`
   يعطل (AttributeError أعيد إنتاجه بالاستدعاء العام)؛ و**فجوة توصيل سجل
   المهارات** — `UniversalSkillFabric` سجلان مستقلان: التسجيل العام لا يصل
   إلى التركيب (أعيد إنتاجه بالفحص: compose يرجع [] لمهارة مسجلة عبر
   الواجهة العامة). كلاهما يوثق عيباً مسمى يُصلح أو يعلن في العمل المسمى.
5. **لا يُعين منسق إدراك**: لا دليل يستند إليه تعيينه — الجهات المرجعية
   وحدودها المعلنة موثقة بمواقعها: فصل النية →
   `agos/agos-kernel/intelligence/intent.py` (مرجع بحدود معلنة: آلية
   محدودة لا مفسر قصد حر)؛ التقييم الحسابي للاختيارات → `decision-pipeline`
   (سياسات ترشيح واختيار — ليس قياس جودة/مخاطر/تكلفة ولا حل قيود
   عاماً)؛ تسجيل القرارات الخارجية → `cognitive/decision.py`. التفويض
   بينها يحتاج توافق عقد لا تشابه اسم.
6. **G2**: كل رموز السطحين العامة تبقى — لا حذف ولا إعادة تسمية اختبارات؛
   الترحيل اللاحق يزيل الادعاءات غير المسندة المحددة ويحفظ العمليات
   المنفذة بحدودها الموثقة.

## التنفيذ المتبقي (أعمال مسماة بحدود ومعايير قبول — لا تنفيذ ضمن هذا البند)

1. **إزالة الادعاءات غير المسندة المحددة بالأدلة** — مع إبقاء العمليات
   المنفذة (السجلات، فحص الفراغ، اختيار أول بديل موثقاً كترتيب).
   **معيار القبول**: اختبارات تثبت الفرق — الادعاء المزال يُصرّح بعدم
   تنفيذه بمسوغ مسمّى، والعمل المنفذ يبقى بنتيجته.
2. **إصلاح أو تعليل عيبي المسار العام**: RelationshipEngine (AttributeError
   المعاد إنتاجه) وفجوة توصيل سجل المهارات (سجلان مستقلان). **معيار
   القبول**: إما قراءة الحواف من المصدر الفعلي ووصول المهارة المسجلة
   إلى compose بنتيجة مثبتة، أو تعليل مسمى — باختبار يثبت كل حالة.
3. **حد سجل النوايا**: إما معرّفات مميزة أو تسمية الاستبدال صراحة.
   **معيار القبول**: اختبار يسجل نيتين ويطابق السلوك الموثق المختار.
4. **تمييز وعود وصف الصنوف غير المنفذة** (بدءاً بـUniversalDecisionPlatform:
   Graph/Simulator/Optimizer). **معيار القبول**: الوصف لا يعد بما لا ينفذ.

## ما لا يقرره هذا ADR

- لا يحذف ولا يعدل كوداً (مخرج البند وثائقي).
- لا يعين منسق إدراك ولا ينقل أي مسؤولية بين الجهات المعتمدة (التفويض
  يحتاج توافق عقد — فجوة مستقلة عند ظهور استعمال فعلي).
- لا يدعي أن التوحيد التشغيلي نُفّذ.
