# سجل الوحدات — AGOS Module Register

> مُولَّد آلياً بواسطة `tools/audit/module_register.py` من `docs/audit/inventory.json`. لا تحرره يدوياً.
> المستويات (ADR-0003): L0 ميت · L1 قابل للاستيراد · L2 متصل بمسار التشغيل · L3 مختبَر · L4 حقيقي (متصل + مختبَر + بلا دوال فارغة).
> **هدف المشروع: كل وحدة تصل إلى L4.**

## ملخص المستويات

- **L0**: 0 حزمة
- **L1**: 111 حزمة
- **L2**: 8 حزمة
- **L3**: 3 حزمة
- **L4**: 12 حزمة

## الطبقات

- **L0** — القانون والمواصفات / Law & Specifications
- **L1** — نواة الأساس / Kernel Core
- **L2** — تشغيل النواة / Kernel Runtime
- **L3** — نسيج القدرات / Capability Fabric (capabilities, providers, skills, adapters, packs)
- **L4** — الذكاء والمعرفة / Intelligence & Knowledge
- **L5** — الحضارة والمنصة / Civilization & Platform layers
- **L6** — المؤسسة والنظام البيئي والسحابة والمنتجات / Enterprise, Ecosystem, Cloud, Products

## حزم الكود

| layer | package | concept | files | lines | stub fns | imports | connected | tested | level | roadmap items |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | `__init__.py` | namespace | 1 | 168 | 0 | yes | no | yes | L1 | R-F-005 |
| L1 | `agos-kernel/agos_kernel` | namespace | 1 | 14 | 0 | yes | no | yes | L1 | R-F-003, R-F-005 |
| L1 | `agos-kernel/architecture` | governance | 1 | 220 | 0 | yes | no | no | L1 | R-W1-001 |
| L1 | `agos-kernel/bootstrap` | boot | 1 | 277 | 0 | yes | no | no | L1 | R-W3-001 |
| L1 | `agos-kernel/bootstrapper` | boot | 1 | 217 | 0 | yes | yes | yes | L4 | R-F-004, R-W3-001 |
| L1 | `agos-kernel/container` | boot | 1 | 165 | 0 | yes | yes | no | L2 | R-W3-001 |
| L1 | `agos-kernel/context` | execution | 1 | 61 | 0 | yes | yes | no | L2 | R-W3-003 |
| L1 | `agos-kernel/contract_engine` | contracts | 1 | 360 | 0 | yes | yes | yes | L4 | R-W1-019 |
| L1 | `agos-kernel/contracts` | contracts | 1 | 124 | 0 | yes | yes | no | L2 | R-W1-019 |
| L1 | `agos-kernel/core` | core-brain | 24 | 3695 | 0 | yes | no | yes | L1 | R-F-002, R-F-008, R-W3-003, R-W1-022 |
| L1 | `agos-kernel/decision` | decision | 1 | 86 | 0 | yes | no | yes | L1 | R-F-007, R-W3-004 |
| L1 | `agos-kernel/decision-pipeline` | decision | 1 | 305 | 0 | yes | no | no | L1 | R-F-004, R-W3-004 |
| L1 | `agos-kernel/decision_pipeline` | decision | 1 | 18 | 0 | yes | no | no | L1 | R-F-004, R-W3-004 |
| L1 | `agos-kernel/diagnostics` | healing | 3 | 159 | 0 | yes | no | yes | L1 | R-F-007, R-W3-013 |
| L1 | `agos-kernel/discovery` | registry | 1 | 442 | 0 | yes | yes | yes | L4 | R-W3-002 |
| L1 | `agos-kernel/event-engine` | events | 1 | 211 | 0 | yes | yes | no | L2 | R-F-004, R-W3-005 |
| L1 | `agos-kernel/event_engine` | events | 1 | 18 | 0 | yes | yes | no | L2 | R-F-004, R-W3-005 |
| L1 | `agos-kernel/events` | events | 1 | 75 | 0 | yes | yes | yes | L4 | R-W3-005 |
| L1 | `agos-kernel/execution-context` | execution | 1 | 248 | 0 | yes | no | no | L1 | R-F-004, R-W3-003 |
| L1 | `agos-kernel/execution_context` | execution | 1 | 18 | 0 | yes | no | no | L1 | R-F-004, R-W3-003 |
| L1 | `agos-kernel/interfaces` | contracts | 1 | 80 | 0 | yes | yes | yes | L4 | R-W1-019 |
| L1 | `agos-kernel/mission` | mission | 1 | 46 | 0 | yes | yes | yes | L4 | R-W3-003 |
| L1 | `agos-kernel/models` | object-model | 1 | 292 | 0 | yes | no | no | L1 | R-W1-012 |
| L1 | `agos-kernel/policies` | governance | 1 | 109 | 0 | yes | no | yes | L1 | R-W4-005 |
| L1 | `agos-kernel/registry` | registry | 3 | 123 | 0 | yes | yes | yes | L4 | R-W3-002 |
| L1 | `agos-kernel/resolvers` | registry | 1 | 206 | 0 | yes | yes | yes | L4 | R-W3-002 |
| L1 | `agos-kernel/shared` | contracts | 1 | 60 | 0 | yes | yes | yes | L4 | R-W1-019 |
| L1 | `agos_kernel` | namespace | 1 | 172 | 0 | yes | no | no | L1 | R-F-003, R-F-005 |
| L2 | `agos-kernel` | quality | 23 | 5545 | 0 | yes | yes | yes | L4 | R-F-002, R-F-008, R-Q-001 |
| L2 | `agos-kernel/agos_runtime` | boot | 1 | 139 | 0 | yes | yes | yes | L4 | R-W3-001 |
| L2 | `agos-kernel/api` | products-api | 2 | 342 | 1 | yes | no | yes | L1 | R-W4-007 |
| L2 | `agos-kernel/approval` | human-loop | 2 | 184 | 0 | yes | no | yes | L1 | R-W3-015 |
| L2 | `agos-kernel/collaboration` | human-loop | 2 | 238 | 0 | yes | no | yes | L1 | R-W3-015 |
| L2 | `agos-kernel/crossdomain` | mission | 2 | 382 | 0 | yes | no | yes | L1 | R-W4-013 |
| L2 | `agos-kernel/distributed` | cloud | 2 | 316 | 0 | yes | no | yes | L1 | R-W4-008 |
| L2 | `agos-kernel/execution` | execution | 5 | 1466 | 0 | yes | no | yes | L1 | R-W3-003 |
| L2 | `agos-kernel/finalization` | quality | 1 | 1142 | 0 | yes | no | no | L1 | R-W5-002 |
| L2 | `agos-kernel/governance` | governance | 2 | 535 | 0 | yes | no | yes | L1 | R-W1-007, R-W3-015 |
| L2 | `agos-kernel/hardening` | quality | 1 | 404 | 0 | yes | no | no | L1 | R-F-007, R-Q-007 |
| L2 | `agos-kernel/healing` | healing | 2 | 195 | 4 | yes | no | yes | L1 | R-W3-013 |
| L2 | `agos-kernel/longrunning` | mission | 1 | 1 | 0 | yes | no | no | L1 | R-W3-003 |
| L2 | `agos-kernel/mission-engine` | mission | 1 | 248 | 0 | yes | yes | no | L2 | R-F-004, R-W3-003 |
| L2 | `agos-kernel/mission_engine` | mission | 1 | 18 | 0 | yes | yes | yes | L4 | R-F-004, R-W3-003 |
| L2 | `agos-kernel/observability` | observability | 1 | 441 | 0 | yes | no | no | L1 | R-W3-008 |
| L2 | `agos-kernel/orchestrator` | cloud | 2 | 362 | 1 | yes | no | yes | L1 | R-W4-008 |
| L2 | `agos-kernel/organization` | human-loop | 2 | 183 | 0 | yes | no | yes | L1 | R-W3-015 |
| L2 | `agos-kernel/pipeline` | execution | 1 | 166 | 0 | yes | yes | no | L2 | R-W3-003 |
| L2 | `agos-kernel/platform_runtime` | civilization | 2 | 232 | 0 | yes | no | yes | L1 | R-W1-009, R-W3-014 |
| L2 | `agos-kernel/quality_gates` | quality | 1 | 443 | 0 | yes | no | yes | L1 | R-W4-004 |
| L2 | `agos-kernel/resource-manager` | runtime | 1 | 222 | 0 | yes | no | no | L1 | R-F-004, R-W3-007 |
| L2 | `agos-kernel/resource_manager` | runtime | 1 | 18 | 0 | yes | no | no | L1 | R-F-004, R-W3-007 |
| L2 | `agos-kernel/runtime` | runtime | 29 | 3373 | 0 | yes | no | yes | L1 | R-W3-006, R-W3-007 |
| L2 | `agos-kernel/scheduler` | runtime | 1 | 273 | 0 | yes | no | no | L1 | R-W3-007 |
| L2 | `agos-kernel/self_hosting` | evolution | 1 | 379 | 0 | yes | no | no | L1 | R-W5-008 |
| L2 | `agos-kernel/simulation` | simulation | 2 | 342 | 1 | yes | no | yes | L1 | R-W3-012 |
| L2 | `agos-kernel/skill-engine` | skills | 1 | 209 | 1 | yes | no | no | L1 | R-F-004, R-W3-009 |
| L2 | `agos-kernel/skill_engine` | skills | 1 | 18 | 0 | yes | no | no | L1 | R-F-004, R-W3-009 |
| L2 | `agos-kernel/state-store` | runtime | 1 | 286 | 0 | yes | no | no | L1 | R-F-004, R-W3-006 |
| L2 | `agos-kernel/state_store` | runtime | 1 | 18 | 0 | yes | no | no | L1 | R-F-004, R-W3-006 |
| L2 | `agos-kernel/trust` | human-loop | 2 | 254 | 0 | yes | no | yes | L1 | R-W3-015 |
| L2 | `agos-kernel/v2` | civilization | 2 | 228 | 0 | yes | no | yes | L1 | R-W1-009, R-W3-014 |
| L2 | `agos-kernel/verification` | human-loop | 2 | 224 | 0 | yes | no | yes | L1 | R-W3-015 |
| L2 | `agos-kernel/vertical_slices` | mission | 1 | 413 | 0 | yes | no | yes | L1 | R-W3-003 |
| L2 | `cli.py` | boot | 1 | 29 | 0 | yes | no | yes | L1 | R-F-001, R-W3-001 |
| L3 | `agos-kernel/adapters` | providers | 11 | 1343 | 9 | yes | no | yes | L1 | R-W3-011 |
| L3 | `agos-kernel/agent_packs` | packs | 1 | 141 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/capabilities` | repository-intelligence | 10 | 2736 | 26 | yes | yes | yes | L3 | R-W2-001, R-W2-002, R-W2-003, R-W2-004, R-W2-007 |
| L3 | `agos-kernel/civilization_packs` | packs | 1 | 206 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/cloud_packs` | packs | 1 | 111 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/connectors` | packs | 1 | 133 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/domains` | domains | 3 | 565 | 0 | yes | no | yes | L1 | R-W4-013 |
| L3 | `agos-kernel/extension` | sdk | 2 | 312 | 5 | yes | no | yes | L1 | R-W4-002 |
| L3 | `agos-kernel/framework_packs` | packs | 1 | 135 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/language_packs` | packs | 1 | 107 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/model_packs` | packs | 1 | 149 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/providers` | providers | 7 | 1542 | 26 | yes | yes | yes | L3 | R-W2-005, R-W3-010 |
| L3 | `agos-kernel/repository` | repository-intelligence | 2 | 309 | 2 | yes | no | yes | L1 | R-W2-006 |
| L3 | `agos-kernel/sdk` | sdk | 2 | 353 | 4 | yes | no | yes | L1 | R-W4-001 |
| L3 | `agos-kernel/sdks` | sdk | 3 | 545 | 9 | yes | no | no | L1 | R-W4-001 |
| L3 | `agos-kernel/skills` | skills | 10 | 1651 | 48 | yes | no | yes | L1 | R-W3-009 |
| L3 | `agos-kernel/stack_detection` | repository-intelligence | 1 | 1147 | 0 | yes | yes | no | L2 | R-W2-001, R-W2-002, R-W2-006 |
| L3 | `agos-kernel/templates` | packs | 1 | 101 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/tool_packs` | packs | 1 | 144 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `agos-kernel/workflows` | packs | 1 | 228 | 0 | yes | no | yes | L1 | R-W4-005 |
| L3 | `rie` | repository-intelligence | 12 | 2559 | 20 | yes | no | yes | L1 | R-F-006, R-W2-006 |
| L4 | `agos-kernel/audit` | governance | 1 | 148 | 3 | yes | no | yes | L1 | R-W5-002 |
| L4 | `agos-kernel/benchmark` | certification | 3 | 347 | 1 | yes | no | yes | L1 | R-W2-011, R-W5-003 |
| L4 | `agos-kernel/brain` | core-brain | 2 | 258 | 0 | yes | no | yes | L1 | R-W1-011, R-W3-014 |
| L4 | `agos-kernel/certification` | certification | 3 | 494 | 6 | yes | no | yes | L1 | R-W4-004 |
| L4 | `agos-kernel/evolution` | evolution | 4 | 1264 | 44 | yes | no | no | L1 | R-W1-008, R-W5-006 |
| L4 | `agos-kernel/expansion` | evolution | 2 | 182 | 1 | yes | no | no | L1 | R-W5-007 |
| L4 | `agos-kernel/experience` | learning | 2 | 156 | 0 | yes | no | yes | L1 | R-W5-001 |
| L4 | `agos-kernel/intelligence` | intelligence | 16 | 4305 | 0 | yes | no | yes | L1 | R-W1-006, R-W2-006 |
| L4 | `agos-kernel/knowledge` | knowledge | 6 | 1051 | 0 | yes | no | yes | L1 | R-W1-005, R-W2-008 |
| L4 | `agos-kernel/laboratory` | evolution | 2 | 353 | 4 | yes | no | yes | L1 | R-W5-006 |
| L4 | `agos-kernel/learning` | learning | 2 | 186 | 0 | yes | no | yes | L1 | R-W5-001 |
| L4 | `agos-kernel/marketplace` | marketplace | 3 | 391 | 5 | yes | no | yes | L1 | R-W4-003 |
| L4 | `agos-kernel/memory` | learning | 3 | 394 | 0 | yes | no | yes | L1 | R-W5-001 |
| L4 | `agos-kernel/observatory` | observability | 2 | 182 | 1 | yes | no | yes | L1 | R-W1-016, R-W4-011 |
| L4 | `agos-kernel/optimization` | optimization | 2 | 221 | 0 | yes | no | yes | L1 | R-W5-004 |
| L4 | `agos-kernel/prediction` | optimization | 2 | 164 | 0 | yes | no | yes | L1 | R-W5-004 |
| L4 | `agos-kernel/recommendation` | optimization | 2 | 175 | 0 | yes | no | yes | L1 | R-W5-004 |
| L4 | `cognition` | cognition | 6 | 373 | 8 | yes | no | no | L1 | R-W1-010, R-W3-016 |
| L4 | `cognitive` | cognition | 11 | 609 | 6 | yes | no | no | L1 | R-W1-010, R-W3-016 |
| L4 | `intelligence` | intelligence | 6 | 410 | 8 | yes | no | no | L1 | R-F-005, R-W1-006, R-W3-019 |
| L4 | `research` | evolution | 6 | 337 | 5 | yes | no | no | L1 | R-W5-007 |
| L5 | `agos-kernel/civilization` | civilization | 100 | 24065 | 120 | yes | yes | yes | L3 | R-F-003, R-W1-009, R-W3-014 |
| L5 | `civilization` | civilization | 5 | 529 | 16 | yes | no | yes | L1 | R-F-005, R-W1-009, R-W3-014 |
| L5 | `consolidation` | governance | 1 | 66 | 1 | yes | no | no | L1 | R-W1-001 |
| L5 | `constitution` | governance | 2 | 264 | 1 | yes | no | no | L1 | R-W1-022 |
| L5 | `domain` | domains | 6 | 419 | 7 | yes | no | no | L1 | R-W4-013 |
| L5 | `execution` | execution | 11 | 552 | 0 | yes | no | no | L1 | R-F-005, R-W1-003, R-W3-019 |
| L5 | `fabric` | fabric | 6 | 697 | 8 | yes | no | yes | L1 | R-W1-013, R-W3-018 |
| L5 | `foundation` | object-model | 11 | 849 | 4 | yes | no | no | L1 | R-W1-012, R-W3-017 |
| L5 | `governance` | governance | 4 | 437 | 14 | yes | no | no | L1 | R-F-005, R-W1-007 |
| L5 | `meta` | registry | 7 | 626 | 0 | yes | no | no | L1 | R-W1-014, R-W3-017 |
| L5 | `orchestration` | fabric | 1 | 161 | 12 | yes | no | no | L1 | R-W3-018 |
| L5 | `resource` | object-model | 1 | 153 | 2 | yes | no | no | L1 | R-W3-017 |
| L5 | `seos` | fabric | 5 | 1212 | 2 | yes | no | yes | L1 | R-F-005, R-W4-012 |
| L6 | `agos-kernel/ecosystem` | enterprise | 5 | 2258 | 102 | yes | no | no | L1 | R-W1-015, R-W4-009 |
| L6 | `agos-kernel/enterprise` | enterprise | 5 | 2229 | 100 | yes | no | no | L1 | R-W1-015, R-W4-009 |
| L6 | `agos-kernel/federation` | enterprise | 5 | 2034 | 98 | yes | no | no | L1 | R-W1-015, R-W4-009 |
| L6 | `cloud` | cloud | 5 | 612 | 1 | yes | no | yes | L1 | R-F-005, R-W4-008 |
| L6 | `cloud_collaboration` | cloud | 1 | 97 | 0 | yes | no | no | L1 | R-W4-008 |
| L6 | `cloud_execution` | cloud | 1 | 88 | 0 | yes | no | no | L1 | R-W4-008 |
| L6 | `cloud_experience` | cloud | 1 | 102 | 0 | yes | no | no | L1 | R-W4-008 |
| L6 | `cloud_session` | cloud | 1 | 95 | 0 | yes | no | no | L1 | R-W4-008 |
| L6 | `cloud_workspace` | cloud | 1 | 103 | 1 | yes | no | no | L1 | R-W4-008 |
| L6 | `ecosystem` | enterprise | 7 | 249 | 0 | yes | no | yes | L1 | R-F-005, R-W1-015, R-W4-009 |
| L6 | `enterprise` | enterprise | 6 | 357 | 6 | yes | no | no | L1 | R-F-005, R-W1-015, R-W4-009 |
| L6 | `evolution` | evolution | 6 | 405 | 17 | yes | no | no | L1 | R-F-005, R-W1-008, R-W5-006 |
| L6 | `observatory` | observability | 2 | 125 | 10 | yes | no | no | L1 | R-F-005, R-W1-016, R-W4-011 |
| L6 | `products` | products-api | 5 | 556 | 15 | yes | no | no | L1 | R-W4-010 |
| L6 | `sdk` | sdk | 1 | 132 | 3 | yes | no | no | L1 | R-F-005, R-W4-001 |

## حزم الوثائق والمواصفات (L0)

| package | concept | roadmap items |
|---|---|---|
| `agos-canon` | governance | R-W1-007, R-W1-022 |
| `agos-enterprise` | enterprise | R-W1-015 |
| `agos-factory` | evolution | R-W5-009 |
| `agos-intelligence` | intelligence | R-W1-006 |
| `aie-intelligence` | decision | R-W1-004, R-W2-010 |
| `ari-research` | certification | R-W2-011 |
| `cgp-genome` | repository-intelligence | R-W2-012 |
| `constitution (README)` | governance | R-W1-022 |
| `execution-program` | specs | R-G-001 |
| `knowledge-base` | specs | R-W1-024 |
| `rie-sprint1` | repository-intelligence | R-W2-006 |
| `rpp-pipeline` | repository-intelligence | R-W2-013 |
| `sdl-loop` | evolution | R-W5-005 |
| `spec-formal` | specs | R-W1-018 |
| `sprint-000` | specs | R-W1-024 |
