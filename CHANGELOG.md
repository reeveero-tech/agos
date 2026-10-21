# سجل التغييرات — AGOS

> كل مدخل مرتبط ببند في [ROADMAP.md](ROADMAP.md) وسجل عمل في `docs/worklog/` (GOVERNANCE G1).
> الصيغة مبنية على [Keep a Changelog](https://keepachangelog.com/).

## [غير مُصدَر]

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
