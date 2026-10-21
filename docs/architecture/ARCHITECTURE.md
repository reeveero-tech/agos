# معمارية AGOS المعتمدة

> القرار: [ADR-0001](../adr/ADR-0001-canonical-namespace-and-integration.md). البند: R-W1-001.
> سجل كل حزمة وطبقتها: [MODULE_REGISTER.md](MODULE_REGISTER.md).

## الطبقات

```
L6  المؤسسة · النظام البيئي · السحابة · المنتجات   (products, cloud*, enterprise, ecosystem, federation, sdk, observatory)
L5  الحضارة والمنصة                               (civilization, foundation, fabric, meta, resource, orchestration, seos, ...)
L4  الذكاء والمعرفة                               (intelligence, brain, knowledge, memory, learning, cognitive, cognition, ...)
L3  نسيج القدرات                                  (capabilities, providers, skills, adapters, packs, rie, ...)
L2  تشغيل النواة                                  (runtime, scheduler, state-store, mission-engine, pipeline, execution, ...)
L1  نواة الأساس                                   (core, contracts, models, container, registry, events, bootstrapper, ...)
L0  القانون والمواصفات                            (constitution, agos-canon, spec-formal, knowledge-base, execution-program)
```

## قواعد الاعتماد
1. الطبقة تعتمد على ما **تحتها** فقط، عبر **العقود** (`contracts`/`interfaces`) لا عبر التنفيذات.
2. النواة (L1–L2) **لا تعرف** أسماء النماذج أو الوكلاء أو الموفّرين أو الأدوات (الدستور، المادة 3).
3. كل تنفيذ يمر عبر مشغّل المهام (المادة 15) وينتج أحداثاً (المادة 6).
4. الطبقات العليا تتصل بالنواة **بالتسجيل** في السجل الموحد (R-W3-002)، لا بالاستيراد العكسي.

## مسار الإقلاع المعتمد (منفّذ — R-W3-001)

```
agos_runtime.boot()
  └─ Bootstrapper.bootstrap()
       1 configuration  2 Container  3 infrastructure
       4 AutoDiscovery → CapabilityRegistry / ProviderRegistry
       5 contract validation (contract_engine)
       6 EventEngine    7 MissionEngine → ExecutionPipeline → Skills → Providers
       8 platform layers register (L4–L6)  9 kernel ready
```

**الحالة بعد R-W3-001:** الخطوات 1–7 و9 تعمل فعلاً. `main.py` و`agos-analyze` يقلعان عبر
`agos_runtime.boot()`، والتحليل يجري مهمةً في هذا المسار:
`MissionEngine` ← `ExecutionPipeline` ← `CapabilityResolver` ← `ProviderResolver` ← `RepositoryAnalysis`،
وتُنشر أحداثها الأربعة على `EventBus` النواة. أما الخطوة 8، تسجيل طبقات المنصة، فتُستكمل في R-W3-002.
ما تبقى للبنود اللاحقة:
- القدرة تستدعي `LocalRepositoryProvider` مباشرة، لا الموفّر المحلول. هذا نطاق R-W3-003.
- القدرات الفرعية `capabilities/analysis|repository|technology` والموفّرون المبنيون على `providers.base.Provider` غير مسجلين بعد، ويظهرون **تحذيرات** إقلاع. هذا نطاق R-W3-002.

## مساحات الأسماء (ADR-0001)
| الكود | الاستيراد القديم (يبقى يعمل) | الاستيراد الموحد |
|---|---|---|
| النواة | `from container import Container` (مع `agos-kernel` على المسار) | `agos.kernel.container` · `agos_kernel.container` |
| حزم الشرطة | غير ممكن سابقاً | `event_engine`, `mission_engine`, `skill_engine`, `decision_pipeline`, `execution_context`, `resource_manager`, `state_store` |
| الوحدات الخارجية | `import cognitive` (مع `agos/` على المسار) | `agos.cognitive` |
