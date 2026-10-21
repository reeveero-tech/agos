# AGOS — Autonomous General Orchestration System

**نظام تشغيل للهندسة البرمجية الذاتية** — «دماغ واحد، موفّرون كثيرون». نواة صغيرة حتمية تملك النية والتخطيط والقرار والمعرفة وحالة المهمة، وكل نموذج أو وكيل أو أداة موفّرٌ قابل للاستبدال خلف عقد. انظر [الدستور](agos/constitution/README.md) و[وثيقة الرؤية](agos/knowledge-base/phase-9/07-Vision-Document.md).

> **حالة المشروع:** قيد الإكمال وفق [خارطة الطريق](ROADMAP.md). الحالة الحية والخطوة التالية في [PROJECT_STATE.md](PROJECT_STATE.md).

## للمساهمين — ابدأ هنا
1. [GOVERNANCE.md](GOVERNANCE.md) — **قاعدتان مفروضتان آلياً:** كل التزام يحمل عمله وتوثيقه وتحديث الخارطة والحالة معاً، و**يُمنع الحذف**.
2. [PROJECT_STATE.md](PROJECT_STATE.md) — أين وصلنا وما الخطوة التالية.
3. [ROADMAP.md](ROADMAP.md) — كل البنود بمعايير قبولها.
4. [docs/architecture/MODULE_REGISTER.md](docs/architecture/MODULE_REGISTER.md) — كل حزمة وطبقتها ومستوى حياتها.

```bash
uv sync --frozen                          # Python 3.12
bash tools/governance/install_hooks.sh    # خطافات الحوكمة
python tools/quality/run_tests.py         # الاختبارات (بلا تراجع عن خط الأساس)
python tools/audit/inventory.py && python tools/audit/module_register.py   # الجرد وسجل الوحدات
```

## التشغيل الحالي
```bash
cd agos/agos-kernel && python main.py <git-url> [--branch main]   # يُنتج RepositoryDNA.json
```

## البنية
| المسار | المحتوى |
|---|---|
| `agos/agos-kernel/` | النواة (95 حزمة) |
| `agos/` | طبقات المنصة (cognitive, foundation, fabric, cloud, products, ...) |
| `agos/knowledge-base/`, `agos/constitution/`, `agos/agos-canon/`, `agos/spec-formal/` | القانون والمواصفات وقاعدة المعرفة |
| `tools/` | الحوكمة والجرد والجودة |
| `docs/` | الدراسة، المعمارية، ADRs، سجلات العمل |
