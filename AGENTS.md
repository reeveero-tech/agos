# تعليمات لأي وكيل/مطوّر يعمل على AGOS

1. **اقرأ أولاً:** `PROJECT_STATE.md` (ابدأ من هنا + الخطوة التالية) ثم `GOVERNANCE.md`.
2. **لا تحذف أي شيء** (ملفات، نقل، إعادة تسمية، دوال/أصناف عامة). حسّن أو أضف أو أوقف بشكل منظم (ADR-0002).
3. **كل التزام = عمل + توثيق:** رسالة فيها `[R-X-NNN]` + تحديث `ROADMAP.md` و`PROJECT_STATE.md` و`CHANGELOG.md` + ملف في `docs/worklog/`.
4. ثبّت الخطافات: `bash tools/governance/install_hooks.sh`.
5. شغّل قبل الالتزام: `python tools/quality/run_tests.py`، `python tools/audit/inventory.py`، `python tools/audit/module_register.py`.
6. لا تكرر عملاً: تحقق من حالة البند في `ROADMAP.md` وسجلات `docs/worklog/`.
7. أي حزمة جديدة تُسجَّل في `tools/audit/module_map.py`.

English: read PROJECT_STATE.md first; never delete; every commit carries its roadmap id and updates ROADMAP/PROJECT_STATE/CHANGELOG/worklog in the same commit.
