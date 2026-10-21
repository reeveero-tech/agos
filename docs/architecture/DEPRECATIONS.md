# سجل الإيقاف المنظَّم (لا شيء يُحذف — ADR-0002)

| العنصر | السبب | البديل | البند | التاريخ |
|---|---|---|---|---|
| `agos/push_to_github.sh` | يستهدف مستودعاً آخر (`reeveero-tech/All-hand`) بمسارات `/workspace` ثابتة؛ ليس جزءاً من دورة عمل هذا المستودع | `git push` العادي مع خطافات الحوكمة (`tools/governance/install_hooks.sh`) | R-G-007 | 2026-10-21 |
| `replit.md` | وثيقة بيئة Replit السابقة؛ تشير إلى مواصفة `attached_assets` غير موجودة في المستودع | `README.md` + `PROJECT_STATE.md` | R-G-007 | 2026-10-21 |
| `agos/agos-kernel/finalization/reports/*` | تقارير ذاتية تعلن «CERTIFIED v1.0» بلا اختبارات ناجحة | تقارير يولدها R-W5-002 من نتائج فعلية | R-W5-002 | 2026-10-21 |
