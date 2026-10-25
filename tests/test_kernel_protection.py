"""حماية النواة — المادة 16: «لا شيء يعدّل النواة. أبداً.» (سجل العمل 0091).

منهج المشروع: أحمر أولاً — هذه الاختبارات تُثبت الثغرة (الكتابة إلى شجرة
النواة ممكنة اليوم عبر منافذ الكتابة بلا أي احتواء) ثم يُصلح بأدنى تغيير:
حارس وقت تشغيل (architecture/kernel_protection.py) يرفض الكتابة إلى محتوى
النواة، بقاعدة مطابقة لتعريف التجميد في freeze.py (كل الملفات عدا
__pycache__ و*.pyc — نواتج التنفيذ لا تعدل النواة)، والمسارات تُحل إلى
مسارها الحقيقي فلا تجاوز بمسار نسبي صاعد ولا برابط رمزي.
"""
import json
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
KERNEL = REPO / "agos" / "agos-kernel"
PROBE = KERNEL / "_kernel_protection_probe.py"  # ملف اختبار داخل الشجرة — يُنظف دائماً


def run(code: str, cwd: Path = KERNEL) -> str:
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=cwd,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


@pytest.fixture(autouse=True)
def _cleanup_probe():
    """الملف التجريبي لا يبقى في شجرة النواة مهما كانت نتيجة الاختبار."""
    yield
    PROBE.unlink(missing_ok=True)
    (KERNEL / "_kernel_protection_probe_target.py").unlink(missing_ok=True)
    (KERNEL / "_kernel_protection_probe_tar.py").unlink(missing_ok=True)


def test_filesystem_provider_refuses_kernel_write(tmp_path):
    """المنفذ الأول: FileSystemProvider.write يكتب اليوم في شجرة النواة بلا
    أي احتواء — يجب أن يرفض (PermissionError صريح) ولا يُنشئ الملف."""
    out = json.loads(run(f"""
        import json
        from providers.filesystem import FilesystemProvider
        probe = {str(PROBE)!r}
        result = {{"raised": False, "returned": None, "exists_after": None}}
        try:
            result["returned"] = FilesystemProvider().write(probe, "probe")
        except PermissionError as e:
            result["raised"] = True
            result["message_ok"] = "المادة 16" in str(e)
        import os
        result["exists_after"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    # الرفض صريح لا صامت: PermissionError بسبب واضح، لا نجاح وهمي
    assert out["raised"] is True
    assert out.get("message_ok") is True
    # ولم يُكتب شيء — الشجرة لم تُمس
    assert out["exists_after"] is False


def test_filesystem_provider_refuses_relative_escape(tmp_path):
    """تجاوز المسار النسبي: مسار بصعود (..) يحل داخل شجرة النواة يُرفض —
    الحارس يحل المسار إلى مساره الحقيقي قبل الفحص."""
    sneaky = str(KERNEL / "sub" / ".." / ".." / "agos-kernel" / "_kernel_protection_probe.py")
    out = json.loads(run(f"""
        import json, os
        from providers.filesystem import FilesystemProvider
        sneaky = {sneaky!r}
        result = {{"raised": False}}
        try:
            FilesystemProvider().write(sneaky, "probe")
        except PermissionError:
            result["raised"] = True
        result["exists_after"] = os.path.exists(sneaky)
        print(json.dumps(result))
    """))
    assert out["raised"] is True
    assert out["exists_after"] is False


def test_filesystem_provider_refuses_symlink_bypass(tmp_path):
    """تجاوز الرابط الرمزي: رابط في مجلد خارجي يشير داخل شجرة النواة —
    الكتابة عبره تُرفض (الحل الحقيقي للرابط يكشف الهدف داخل الشجرة)."""
    link = tmp_path / "escape_link.py"
    target = KERNEL / "_kernel_protection_probe_target.py"
    out = json.loads(run(f"""
        import json, os
        from providers.filesystem import FilesystemProvider
        link = {str(link)!r}
        target = {str(target)!r}
        os.symlink(target, link)
        result = {{"raised": False}}
        try:
            FilesystemProvider().write(link, "probe")
        except PermissionError:
            result["raised"] = True
        result["exists_after"] = os.path.exists(target)
        print(json.dumps(result))
    """))
    assert out["raised"] is True
    assert out["exists_after"] is False


def test_civilization_write_file_refuses_kernel_escape(tmp_path):
    """المنفذ الثاني: FilesystemProvider الحضاري (root/path) — الصعود خارج
    الجذر إلى شجرة النواة يُرفض."""
    out = json.loads(run(f"""
        import json, os
        from agos_kernel.civilization.providers.filesystem_provider import FilesystemProvider
        root = {str(tmp_path)!r}
        kernel_probe = {str(PROBE)!r}
        provider = FilesystemProvider(root)
        # صعود من الجذر إلى ملف داخل شجرة النواة
        rel = os.path.relpath(kernel_probe, root)
        result = {{"raised": False}}
        try:
            provider.write_file(rel, "probe")
        except PermissionError:
            result["raised"] = True
        result["exists_after"] = os.path.exists(kernel_probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True
    assert out["exists_after"] is False


def test_archive_extract_refuses_kernel_escape(tmp_path):
    """المنفذ الثالث: ArchiveProvider.extract — عضو أرشيف يهرب من وجهته
    إلى شجرة النواة (اجتياز المسار) يُرفض، لا يُكتب شيء داخل الشجرة."""
    dest = tmp_path / "dest"
    dest.mkdir()
    # عضو tar يصعد من الوجهة إلى ملف داخل شجرة النواة
    import os as _os
    member = _os.path.relpath(PROBE, dest).replace(_os.sep, "/")
    tar_path = tmp_path / "evil.tar"
    with tarfile.open(tar_path, "w") as tf:
        info = tarfile.TarInfo(member)
        data = b"probe"
        info.size = len(data)
        tf.addfile(info, __import__("io").BytesIO(data))
    out = json.loads(run(f"""
        import json, os
        from providers.filesystem import ArchiveProvider
        result = {{"raised": False, "extracted": None}}
        try:
            result["extracted"] = ArchiveProvider().extract({str(tar_path)!r}, {str(dest)!r})
        except PermissionError:
            result["raised"] = True
        result["exists_after"] = os.path.exists({str(PROBE)!r})
        print(json.dumps(result))
    """))
    # الرفض صريح، والاستخراج لم يكتب داخل الشجرة
    assert out["raised"] is True
    assert out["exists_after"] is False
