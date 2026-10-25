"""حماية النواة وقت التشغيل (المادة 16): «لا شيء يعدّل النواة. أبداً.»

الإنفاذ الفعلي لا التصنيف النصي وحده: التجميد (architecture/freeze.py)
يوثق المحتوى ويراقبه عند الالتزام، وهذه الوحدة تمنع الكتابة وقت التشغيل —
كل منفذ كتابة يرفض الكتابة إلى محتوى النواة.

تعريف «محتوى النواة» هنا مطابق لتعريف التجميد في freeze.py (مصدر واحد
للقاعدة): كل الملفات تحت شجرة النواة عدا أدلة __pycache__ وملفات *.pyc
(نواتج تنفيذ لا محتوى مصدر — كتابتها لا تعدل النواة).

المسارات تُحل إلى مسارها الحقيقي (resolve) قبل الفحص — فلا يُتجاوز الحد
بمسار نسبي صاعد (../) ولا برابط رمزي يشير داخل الشجرة.
"""
from pathlib import Path
from typing import Any

# جذر شجرة النواة — من موقع هذه الوحدة نفسها (architecture/ داخل الشجرة)
KERNEL_TREE_ROOT = Path(__file__).resolve().parents[1]


def is_kernel_content_path(target: Any) -> bool:
    """هل المسار (محلولاً إلى مساره الحقيقي) محتوى نواة محمي؟

    القاعدة مطابقة لتعريف محتوى التجميد في architecture/freeze.py: كل ما
    تحت شجرة النواة عدا __pycache__ و*.pyc. فشل حل المسار يُعامل حمايةً
    (الأمان أولاً — لا يُكتب إلى مسار مجهول الهوية).
    """
    try:
        resolved = Path(target).resolve(strict=False)
    except (OSError, ValueError, TypeError):
        return True  # فشل الحل — حماية أولاً
    try:
        resolved.relative_to(KERNEL_TREE_ROOT)
    except ValueError:
        return False  # خارج شجرة النواة
    # داخل الشجرة: محمي إلا إذا كان ناتج تنفيذ (pycache/pyc) — لا يعدل النواة
    if resolved.suffix == ".pyc":
        return False
    return not any(part == "__pycache__" for part in resolved.parts)


def guard_kernel_write(target: Any) -> None:
    """يرفض كتابة محتوى النواة — إفصاح صريح لا نجاح وهمي (ADR-0008).

    يرفع PermissionError بسبب واضح؛ لا يعيد False صامتاً فلا يبتلع المستدعي
    الرفض على أنه نجاح.
    """
    if is_kernel_content_path(target):
        raise PermissionError(
            "الكتابة إلى محتوى النواة ممنوعة (المادة 16 — لا شيء يعدّل "
            f"النواة. أبداً.): {target}")
