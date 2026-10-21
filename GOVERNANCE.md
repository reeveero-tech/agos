# حوكمة مشروع AGOS — القواعد العليا

> هذه الوثيقة أعلى من أي خطة أو كود في هذا المستودع بعد [الدستور](agos/constitution/README.md).
> أي عمل يخالفها مرفوض آلياً (الخطافات المحلية + CI).
> English summary at the end.

---

## القاعدة G1 — الدفعة الموثّقة الذرية (Atomic Documented Change)

**لا يُنفَّذ أي بند، ولا يُدفع أي التزام، إلا ومعه توثيقه في نفس الالتزام.**
العمل والتوثيق وتحديث الخارطة وحالة المشروع = **التزام واحد**، لا التزامات منفصلة.

كل التزام يجب أن يحتوي في الوقت نفسه على:

| # | المطلوب | الملف |
|---|---|---|
| 1 | معرّف بند من الخارطة في رسالة الالتزام بالشكل `[R-F-003]` (يجب أن يكون موجوداً في الخارطة) | رسالة الالتزام |
| 2 | تحديث حالة البند وملاحظاته | `ROADMAP.md` |
| 3 | تحديث الحالة الراهنة + «الخطوة التالية» + المقاييس | `PROJECT_STATE.md` |
| 4 | مدخل يصف ما تغيّر | `CHANGELOG.md` |
| 5 | سجل عمل تفصيلي (ماذا، لماذا، كيف تم التحقق، ما المتبقي) | `docs/worklog/NNNN-<ID>.md` |

الهدف: أي شخص (إنسان أو وكيل ذكي) يأتي لاحقاً يقرأ `PROJECT_STATE.md` فيعرف **من أين يبدأ بالضبط**، ولا يكرر عملاً أُنجز.

## القاعدة G2 — منع الحذف (No Deletion)

**يُمنع الحذف منعاً باتاً. يجوز التحسين والتطوير والإضافة فقط.**

ممنوع:
- حذف أي ملف أو مجلد.
- نقل أو إعادة تسمية أي ملف (النقل = حذف المسار القديم).
- إزالة أي دالة/صنف عام من المستوى الأعلى، أو أي دالة عامة داخل صنف، من أي وحدة Python.
- حذف فرع بعيد.

مسموح:
- تحسين جسم الدالة وإصلاحه وإعادة كتابة منطقه الداخلي.
- إضافة ملفات ووحدات وأصناف ودوال جديدة.
- إضافة طبقات توافق (aliases / facades / shims) لربط القديم بالجديد.
- **الإيقاف المنظَّم (Deprecation):** إذا تقادم شيء يُعلَّم ويوجَّه إلى البديل، ولا يُحذف — انظر [ADR-0002](docs/adr/ADR-0002-no-deletion-and-deprecation.md).

> ملاحظة: تعديل سطر داخل دالة لتحسينه (مثل استبدال مسار ثابت بمسار محمول) تحسين مسموح، وليس حذفاً.

---

## بروتوكول العمل (لكل من يعمل في المشروع)

1. **ابدأ دائماً من** [`PROJECT_STATE.md`](PROJECT_STATE.md) — قسم «ابدأ من هنا».
2. ثبّت الخطافات مرة واحدة: `bash tools/governance/install_hooks.sh`.
3. اختر البند المحدد في «الخطوة التالية» (أو بنداً حالته `TODO` وتبعياته منجزة) من [`ROADMAP.md`](ROADMAP.md).
4. غيّر حالته إلى `DOING` أثناء العمل (في نفس الالتزام النهائي أو التزام تمهيدي موثق).
5. نفّذ العمل + الاختبارات.
6. شغّل: `python tools/quality/run_tests.py` و `python tools/audit/inventory.py`.
7. حدّث: `ROADMAP.md` + `PROJECT_STATE.md` + `CHANGELOG.md` + `docs/worklog/NNNN-<ID>.md`.
8. التزام واحد برسالة: `[R-X-NNN] وصف مختصر`.
9. الخطاف `pre-commit`/`commit-msg` يتحقق محلياً، والـ CI يعيد التحقق من **كل** التزام مدفوع.

### حالات البنود
| الحالة | المعنى |
|---|---|
| `TODO` | لم يبدأ |
| `DOING` | قيد التنفيذ |
| `DONE` | أُنجز وتحقق منه بمعيار القبول المذكور |
| `PARTIAL` | أُنجز جزء موثق، والمتبقي مذكور في الملاحظات |
| `BLOCKED` | متوقف على قرار أو مورد خارجي (يُذكر السبب) |

### الإنفاذ الآلي
- `tools/governance/check_commit.py` — بوابة الحوكمة (G1 + G2).
- `.githooks/` — `pre-commit`, `commit-msg`, `pre-push`.
- `.github/workflows/governance.yml` — يفحص كل التزام في كل دفع/طلب دمج، ويشغّل الاختبارات.
- `tools/quality/run_tests.py` — مشغّل اختبارات بمبدأ «السقّاطة» (ratchet): يمنع أي تراجع عن خط الأساس.

### نطاق السريان
تسري القواعد ابتداءً من الالتزام الذي أدخل هذه الوثيقة. الالتزام الأول `b9ca3e9` سابق لها ومحفوظ كما هو.

---

## English summary

- **G1 — Atomic documented change:** every commit must carry, in the same commit, a roadmap id in the message (`[R-F-003]`), and updates to `ROADMAP.md`, `PROJECT_STATE.md`, `CHANGELOG.md` and a `docs/worklog/` entry. Work and its documentation are never pushed separately.
- **G2 — No deletion:** no file deletion, no rename/move, no removal of public functions/classes/methods, no remote-branch deletion. Improve, extend, add, or deprecate (ADR-0002) instead.
- Enforced by `tools/governance/check_commit.py` via git hooks (`.githooks/`) and CI.
