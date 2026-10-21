"""حماية الاستنساخ — المصدر الواحد لكل استنساخ في المشروع (R-W2-005).

الاستنساخ عملية على حدود النظام: تُنزل بيانات من خارج الثقة إلى قرص محلي.
قبل هذا البند كان كل موقع استنساخ يقرر لنفسه: بلا مهلة (تعليق أبدي ممكن)،
وبلا قائمة سماح (أي عنوان يُقبل)، وبلا سقوف (مستودع بجيجابايتات يملأ القرص)،
وبلا تنظيف عند الفشل (المجلد المؤقت يبقى يتيمة)، وبلا فحص روابط رمزية
(رابط يهرب إلى خارج المستودع يقرأ ما لا يُقرأ)، والفرع "main" مفترض
(مستودعات "master" تفشل بلا سبب).

القواعد هنا واحدة لكل المسارات (النواة وrie والشريحة وseos):

| الضمانة | التنفيذ |
|---|---|
| مهلة | ``timeout`` على عملية git (افتراضي 300 ثانية) |
| قائمة سماح | ``check_url`` — البادئات المسموحة فقط، وقابلة للتوسيع عند النداء |
| سقوف حجم/عدد | قياس فعلي بعد الاستنساخ: عدد الملفات وحجمها مقابل حدين |
| تنظيف مؤقت دائماً | المجلد المؤقت يُحذف عند أي فشل (finally) — النجاح يسلّمه للمستدعي |
| حماية الروابط الرمزية | ``escape_symlinks`` — أي رابط يحلّ خارج جذر المستودع يُرفض |
| الفرع الافتراضي | فشل الفرع المطلوب ← اكتشاف الفرع الافتراضي (``git ls-remote --symref``) وإعادة المحاولة به مرة واحدة |

الوحدة نقية (مكتبة Python القياسية فقط) ولا تعرف شيئاً عن النواة.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

__all__ = [
    "CloneRejected",
    "check_url",
    "default_branch",
    "clone",
    "measure_repo",
    "escape_symlinks",
    "ALLOWED_URL_PREFIXES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_REPO_BYTES",
    "DEFAULT_MAX_REPO_FILES",
]

# المهلة والسقوف — قيم افتراضية حذرة، قابلة للضبط عند كل نداء.
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_REPO_BYTES = 500 * 1024 * 1024   # 500MB
DEFAULT_MAX_REPO_FILES = 50_000

# قائمة السماح: مضيفون معروفون + file:// للاختبار والتشغيل المحلي + صيغ SSH.
# ليست أمناً مطلقاً — هي حد أدنى يمنع الاستنساخ من عناوين عشوائية (SSRF-ish).
ALLOWED_URL_PREFIXES: Tuple[str, ...] = (
    "https://github.com/", "http://github.com/",
    "https://gitlab.com/", "http://gitlab.com/",
    "https://bitbucket.org/", "http://bitbucket.org/",
    "https://git.sr.ht/", "file://",
    "git@github.com:", "git@gitlab.com:",
    "ssh://git@github.com/", "ssh://git@gitlab.com/",
)


class CloneRejected(ValueError):
    """رفض الاستنساخ قبل أو بعد بدئه — السبب في ``reason`` دائماً."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def check_url(url: str, allowlist: Optional[Tuple[str, ...]] = None) -> str:
    """تأكيد أن العنوان ضمن قائمة السماح (R-W2-005).

    القائمة تحكم **العناوين البعيدة** (https/ssh/...) — منع الاستنساخ من مضيفين
    عشوائيين. المسار المحلي المطلق مسموح دائماً: المستدعي يملك قرصه أصلاً ولا
    يمنحه الاستنساخ شيئاً جديداً؛ والمسار النسبي مرفوض (غامض تبعاً لمجلد العمل)،
    وكذلك صيغة ``//host/…`` (عنوان بعدي يتخفى في هيئة مسار).
    """
    if not url or not isinstance(url, str):
        raise CloneRejected("url empty")
    if os.path.isabs(url) and not url.startswith("//"):
        return url
    allowed = ALLOWED_URL_PREFIXES if allowlist is None else tuple(allowlist)
    if not url.startswith(allowed):
        raise CloneRejected(
            f"url not in allowlist: {url!r} (allowed prefixes: {', '.join(allowed)})")
    return url


def default_branch(url: str, timeout: int = 60,
                   git_bin: str = "git") -> Optional[str]:
    """الفرع الافتراضي للمستودع من ``git ls-remote --symref``، أو ``None``.

    صيغة المخرج: ``ref: refs/heads/master\tHEAD``. لا يرفع استثناء عند الفشل —
    من يستدعيه يقرر (قد لا تكون هناك شبكة أصلاً).
    """
    try:
        out = subprocess.run(
            [git_bin, "ls-remote", "--symref", url, "HEAD"],
            capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("ref:") and "\tHEAD" in line:
            ref = line.split()[1]
            if ref.startswith("refs/heads/"):
                return ref[len("refs/heads/"):]
    return None


def measure_repo(root: "os.PathLike[str] | str") -> Tuple[int, int]:
    """(عدد الملفات، مجموع الحجم بالبايت) — بلا ``.git``، وبلا نزول للمجلدات المُورَّدة.

    الروابط الرمزية للملفات لا تُحتسب (حجمها حجم الهدف وقد يكون خارج الجذر).
    """
    base = Path(root)
    count = 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d != ".git" and not os.path.islink(os.path.join(dirpath, d))]
        for fname in filenames:
            full = Path(dirpath) / fname
            if full.is_symlink():
                continue
            try:
                total += full.stat().st_size
                count += 1
            except OSError:
                continue
    return count, total


def escape_symlinks(root: "os.PathLike[str] | str") -> List[str]:
    """الروابط الرمزية الهاربة خارج جذر المستودع — حماية القراءة (R-W2-005).

    رابط داخل ``.git`` لا يُفحص (مخلفات استنساخ). الرمز المطلوب: كل رابط يحلّ
    داخل الجذر مسموح؛ ما يحلّ خارجه يُرفض الاستنساج كله بسببه.
    """
    base = Path(root).resolve()
    escapes: List[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d != ".git" and not os.path.islink(os.path.join(dirpath, d))]
        for name in list(dirnames) + list(filenames):
            full = Path(dirpath) / name
            if not full.is_symlink():
                continue
            try:
                resolved = full.resolve()
                if not resolved.is_relative_to(base):
                    escapes.append(full.relative_to(base).as_posix())
            except (OSError, ValueError):
                escapes.append(full.relative_to(base).as_posix())
    return escapes


def clone(
    url: str,
    branch: Optional[str] = None,
    dest: Optional["os.PathLike[str] | str"] = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_REPO_BYTES,
    max_files: int = DEFAULT_MAX_REPO_FILES,
    allowlist: Optional[Tuple[str, ...]] = None,
    depth: Optional[int] = 1,
    git_bin: str = "git",
) -> str:
    """استنساخ محصّن بكل الضمانات الست (R-W2-005). يعيد مسار المستودع.

    ``branch=None``: لا يُمرر ``--branch`` فيختار git الفرع الافتراضي بنفسه.
    ``branch`` صريح وفشل: يُكتشف الفرع الافتراضي ويُعاد المحاولة به مرة واحدة
    (مستودعات ``master`` لم تعد تفشل لأن أحدهم افترض ``main``).

    ``dest=None``: مجلد مؤقت جديد يُضمن حذفه عند أي فشل؛ عند النجاح يبقى
    والمستدعي يملك تنظيفه. ``dest`` صريح: الملكية للمستدعي حتى عند الفشل.

    ``depth=None``: استنساخ كامل بلا ``--depth`` (الافتراضي 1 — ضحل).

    بعد نجاح git نفسه: قياس فعلي للسقوف (عدد/حجم) وفحص الروابط الهاربة —
    تجاوز أي حد يرفض المستودع كاملاً ويحذف المجلد المؤقت.
    """
    check_url(url, allowlist)

    temp_dir: Optional[str] = None
    if dest is None:
        temp_dir = tempfile.mkdtemp(prefix="agos_clone_")
        repo_path = os.path.join(temp_dir, "repo")
    else:
        repo_path = str(dest)

    try:
        _run_clone(git_bin, url, repo_path, branch, depth, timeout)
        # السقوف: قياس فعلي لا حدس — مستودع ضخم يُرفض بسببه كله.
        files, total_bytes = measure_repo(repo_path)
        if files > max_files:
            raise CloneRejected(
                f"repo exceeds file cap: {files} > {max_files} files")
        if total_bytes > max_bytes:
            raise CloneRejected(
                f"repo exceeds size cap: {total_bytes} > {max_bytes} bytes")
        # الروابط الهاربة: قراءة خارج الجذر ممنوعة.
        escapes = escape_symlinks(repo_path)
        if escapes:
            raise CloneRejected(
                f"symlinks escape the repository root: {', '.join(sorted(escapes)[:5])}")
        return repo_path
    except BaseException:
        # تنظيف مؤقت دائماً عند الفشل — النجاح يسلّم الملكية للمستدعي.
        if temp_dir is not None:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _run_clone(git_bin: str, url: str, repo_path: str,
              branch: Optional[str], depth: Optional[int], timeout: int) -> None:
    """تشغيل git clone مع المهلة، مع إعادة محاولة واحدة بالفرع الافتراضي عند فشل الفرع."""
    cmd = [git_bin, "clone", "--quiet"]
    if depth is not None:
        cmd.extend(["--depth", str(depth)])
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([url, repo_path])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    except subprocess.TimeoutExpired:
        raise CloneRejected(f"clone timed out after {timeout}s: {url}")
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "")[:400]
        if branch != "main":
            # التراجع للفرع الافتراضي حقٌّ لمن اعتمد الافتراض الاصطلاحي "main" فقط؛
            # فرع طلبه المستدعي صراحة ولم يوجد خطأٌ يُبلَّغ به، لا فرصة ثانية تخفيه.
            raise CloneRejected(f"clone failed: {stderr.strip()}")
        # "main" المفترض غير موجود؟ مرة واحدة بالفرع الافتراضي الحقيقي.
        fallback = default_branch(url, timeout=min(timeout, 60), git_bin=git_bin)
        if fallback is None or fallback == branch:
            raise CloneRejected(f"clone failed: {stderr.strip()}")
        cmd = [git_bin, "clone", "--quiet"]
        if depth is not None:
            cmd.extend(["--depth", str(depth)])
        cmd.extend(["--branch", fallback, url, repo_path])
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc2:
            detail = (getattr(exc2, "stderr", "") or "")[:400] or str(exc2)
            raise CloneRejected(f"clone failed (branch {branch!r}, then default "
                                f"{fallback!r}): {detail.strip()}")
