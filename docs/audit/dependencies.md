# تدقيق التبعيات الخارجية (R-F-011)

> مُولَّد بـ`tools/audit/dependencies.py`، فلا يُحرَّر يدوياً. `--check` يُفشل CI إن تقادم التقرير أو ظهرت مشكلة.

الملفات المفحوصة: **560** (`agos/` و`tests/` و`tools/`) · المشاكل: **0**

## الاستيرادات الخارجية الفعلية

| الاستيراد | التوزيعة | النطاقات (عدد الملفات) | مُعلن في | الإصدار المقفل |
|---|---|---|---|---|
| `a` | `a` | generated (1) | — | — |
| `c` | `c` | generated (1) | — | — |
| `memory_profiler` | `memory-profiler` | runtime (1) | runtime | 0.61.0 |
| `psutil` | `psutil` | runtime (1) | runtime | 7.2.2 |
| `pytest` | `pytest` | dev (22) | dev | 9.1.1 |
| `requests` | `requests` | generated (3) | runtime | 2.34.2 |
| `yaml` | `pyyaml` | runtime (1) | runtime | 6.0.3 |

## التبعيات المعلنة

| التوزيعة | المجموعة | مستورَدة | الإصدار المقفل | سبب الإبقاء إن لم تُستورد |
|---|---|---|---|---|
| `memory-profiler` | runtime | نعم | 0.61.0 | — |
| `psutil` | runtime | نعم | 7.2.2 | — |
| `pyyaml` | runtime | نعم | 6.0.3 | — |
| `requests` | runtime | لا | 2.34.2 | used by the code the platform generates: the Python SDK/client templates in agos-kernel sdk/, laboratory/ and certification/ runtime.py emit `import requests`; kept so generated clients run in the same environment |
| `pytest` | dev | نعم | 9.1.1 | — |
| `pytest-asyncio` | dev | لا | 1.4.0 | pytest plugin, loaded by pytest through `asyncio_mode = "auto"` (R-F-009), never imported |

## أدوات النظام المستدعاة (ليست حزم بايثون)

| الأداة | الملفات |
|---|---|
| `docker` | 3: `agos/agos-kernel/adapters/implementation.py`, `agos/agos-kernel/providers/filesystem.py`, `agos/agos-kernel/providers/network.py` |
| `find` | 2: `agos/agos-kernel/adapters/implementation.py`, `agos/agos-kernel/skills/implementation.py` |
| `git` | 17: `agos/agos-kernel/adapters/implementation.py`, `agos/agos-kernel/capabilities/__init__.py`, `agos/agos-kernel/civilization/core/civilization_engine.py`, `agos/agos-kernel/civilization/intelligence_pipeline/stages.py` … |
| `kubectl` | 1: `agos/agos-kernel/adapters/implementation.py` |
| `npm` | 1: `agos/agos-kernel/adapters/implementation.py` |
| `podman` | 1: `agos/agos-kernel/providers/network.py` |
| `python` | 1: `agos/agos-kernel/self_hosting/runtime.py` |
| `terraform` | 1: `agos/agos-kernel/adapters/implementation.py` |

## المشاكل

لا توجد.
