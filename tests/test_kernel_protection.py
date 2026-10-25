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


# ---------- الشريحة 0092: حراسة بقية منافذ الكتابة ----------

def test_write_skill_refuses_kernel_write():
    """منفذ مهارة كتابة الملف (skills/file) — كتابة إلى شجرة النواة ترفض
    (فشل صريح بسبب واضح في المخرج، لا نجاح وهمي) ولا يُنشئ الملف."""
    out = json.loads(run(f"""
        import json, os
        from skills.file.operations import WriteFileSkill
        probe = {str(PROBE)!r}
        result = WriteFileSkill().execute({{"path": probe, "content": "x"}})
        print(json.dumps({{"result": result, "exists": os.path.exists(probe)}}))
    """))
    assert out["result"]["success"] is False
    assert "المادة 16" in out["result"]["error"]
    assert out["exists"] is False


def test_delete_skill_refuses_kernel_deletion():
    """منفذ مهارة حذف الملف — الحذف تعديل أيضاً (المادة 16): حذف ملف داخل
    شجرة النواة يُرفض صراحة."""
    out = json.loads(run(f"""
        import json, os
        from skills.file.operations import DeleteFileSkill
        probe = {str(PROBE)!r}
        open(probe, "w").write("x")  # موجود مسبقاً — الحذف هو المطلوب رفضه
        result = DeleteFileSkill().execute({{"path": probe}})
        still = os.path.exists(probe)
        os.remove(probe)  # تنظيف
        print(json.dumps({{"result": result, "still_exists": still}}))
    """))
    assert out["result"]["success"] is False
    assert "المادة 16" in out["result"]["error"]
    assert out["still_exists"] is True


def test_invariants_reporter_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from core.invariants.reporter import InvariantReporter
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            InvariantReporter().save_report(probe)
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_invariants_benchmark_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from core.invariants.benchmark import InvariantBenchmark
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            InvariantBenchmark().export_benchmark(probe)
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_evidence_generator_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from pathlib import Path
        from core.invariants.evidence import EvidenceGenerator, EvidencePackage
        probe_dir = {str(KERNEL)!r}
        result = {{"raised": False}}
        try:
            EvidenceGenerator().export_evidence_package(EvidencePackage(), Path(probe_dir))
        except PermissionError:
            result["raised"] = True
        result["probe"] = os.path.exists(probe_dir + "/_kernel_protection_probe.py")
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["probe"] is False


def test_knowledge_graph_save_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from civilization.knowledge_graph.knowledge_graph import KnowledgeGraph
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            KnowledgeGraph().save(probe)
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_graph_versioning_save_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from civilization.knowledge_graph.knowledge_graph import KnowledgeGraph
        from civilization.knowledge_graph.versioning import GraphVersioning
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            GraphVersioning(KnowledgeGraph()).save_versions(probe)
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_artifact_store_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from civilization.artifact_system.artifact import ArtifactStore, Artifact
        probe_root = {str(KERNEL)!r}
        result = {{"raised": False}}
        try:
            ArtifactStore(storage_path=probe_root).save(Artifact())
        except PermissionError:
            result["raised"] = True
        print(json.dumps(result))
    """))
    assert out["raised"] is True


def test_intelligence_pipeline_save_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from civilization.intelligence_pipeline.pipeline import EngineeringIntelligencePipeline
        from civilization.intelligence_pipeline.intelligence_package import EngineeringIntelligencePackage
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            EngineeringIntelligencePipeline().save_package(EngineeringIntelligencePackage(), probe)
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_engineering_report_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from pathlib import Path
        from civilization.capabilities.engineering_report import EngineeringReporter
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            EngineeringReporter().export_report({{"title": "x"}}, Path(probe))
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_seal_certificate_save_refuses_kernel_write():
    out = json.loads(run(f"""
        import json, os
        from pathlib import Path
        from core.seal import KernelSealCertificate
        probe = {str(PROBE)!r}
        result = {{"raised": False}}
        try:
            KernelSealCertificate(kernel_root=Path({str(KERNEL)!r})).save(Path(probe))
        except PermissionError:
            result["raised"] = True
        result["exists"] = os.path.exists(probe)
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["exists"] is False


def test_no_script_writes_runtime_output_into_kernel_tree():
    """رتشيت المصدر: لا ملف بايثون تحت شجرة النواة يستهدف دليل إخراج داخل
    الشجرة (civilization/output) — المخرجات التشغيلية تُكتب خارجها."""
    offenders = []
    for p in KERNEL.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            if "civilization/output" in p.read_text(encoding="utf-8"):
                offenders.append(p.relative_to(REPO).as_posix())
        except (OSError, UnicodeDecodeError):
            continue
    assert offenders == []


def test_kernel_finalizer_report_dir_outside_tree():
    """دليل تقارير المُنهي غير داخل شجرة النواة — المخرجات خارج الشجرة."""
    out = json.loads(run(f"""
        import json
        from pathlib import Path
        from finalization.kernel_finalizer import REPORT_DIR
        kernel_root = Path({str(KERNEL)!r}).resolve()
        print(json.dumps({{"inside": str(REPORT_DIR.resolve()).startswith(str(kernel_root))}}))
    """))
    assert out["inside"] is False


def test_civilization_engine_output_dir_outside_tree():
    """محرك الحضارة يكتب مخرجاته خارج شجرة النواة."""
    out = json.loads(run(f"""
        import json
        from pathlib import Path
        from civilization.core.civilization_engine import CivilizationEngine
        engine = CivilizationEngine()
        kernel_root = Path({str(KERNEL)!r}).resolve()
        out_dir = Path(str(engine._output_dir)).resolve()
        print(json.dumps({{"inside": kernel_root in out_dir.parents}}))
    """))
    assert out["inside"] is False


# ---------- الشريحة 0093: الرابط الرمزي للمخرجات المحوّلة + تغطية main.py سلوكياً ----------

OUTPUT_LINK = REPO / "agos" / "output"  # دليل المخرجات خارج الشجرة — اختبار الاختطاف بالرابط الرمزي


def _hijack_output_with_symlink():
    """يحول دليل المخرجات إلى رابط رمزي نحو داخل شجرة النواة (سيناريو الاختطاف).

    يعيد أثر الاستعادة (اسم النسخة الاحتياطية إن كان الدليل موجوداً).
    """
    import os
    backup = None
    if OUTPUT_LINK.exists():
        backup = OUTPUT_LINK.with_name("output_test_backup")
        os.rename(OUTPUT_LINK, backup)
    os.symlink(KERNEL / "architecture", OUTPUT_LINK)
    return backup


def _restore_output(backup):
    import os
    OUTPUT_LINK.unlink(missing_ok=True)
    # تنظيف آثار الكتابة داخل الشجرة إن حدثت (مرحلة الأحمر)
    (KERNEL / "architecture" / "brain_test_results.json").unlink(missing_ok=True)
    for d in ("reports", "evidence"):
        p = KERNEL / "architecture" / d
        if p.exists() and p.is_dir():
            for f in p.iterdir():
                f.unlink(missing_ok=True)
            p.rmdir()
    if backup is not None:
        os.rename(backup, OUTPUT_LINK)


@pytest.fixture
def hijacked_output():
    """رابط رمزي للمخرجات نحو شجرة النواة — يُستعاد الدليل الأصلي دائماً."""
    backup = _hijack_output_with_symlink()
    try:
        yield
    finally:
        _restore_output(backup)


def test_run_script_refuses_symlinked_output_dir(hijacked_output):
    """سيناريو اختطاف المخرجات: رابط رمزي من دليل المخرجات نحو داخل شجرة
    النواة — السكربت التشغيلي (مثال المجموعة: run_brain) يجب أن يرفض الكتابة
    (فشل صريح بسبب المادة 16) لا أن يكتب نتائجه داخل الشجرة."""
    import subprocess
    script = KERNEL / "civilization" / "engineering_brain" / "run_brain.py"
    r = subprocess.run([sys.executable, str(script)], cwd=KERNEL,
                       capture_output=True, text=True, timeout=180)
    leaked = (KERNEL / "architecture" / "brain_test_results.json").exists()
    combined = r.stdout + r.stderr
    assert r.returncode != 0, "السكربت نجح وهو يكتب داخل شجرة النواة"
    assert "المادة 16" in combined
    assert leaked is False


def test_finalizer_refuses_symlinked_output_dir(hijacked_output):
    """المُنهي: مع اختطاف دليل المخرجات برابط رمزي نحو الشجرة، إنشاء مولد
    التقارير يجب أن يرفض (PermissionError) لا أن ينشئ أدلة التقارير داخلها."""
    out = json.loads(run(f"""
        import json, os
        result = {{"raised": False, "dirs_created": False}}
        try:
            import finalization.kernel_finalizer as kf
            kf.ReportGenerator(None)
        except PermissionError:
            result["raised"] = True
        arch = {str(KERNEL / 'architecture')!r}
        result["dirs_created"] = os.path.isdir(arch + "/reports") or os.path.isdir(arch + "/evidence")
        print(json.dumps(result))
    """))
    assert out["raised"] is True
    assert out["dirs_created"] is False


def test_civilization_engine_refuses_symlinked_output_dir(hijacked_output):
    """محرك الحضارة: مع اختطاف دليل المخرجات، إنشاء المحرك يجب أن يرفض لا
    أن يقبل مسار مخرجات يحل داخل شجرة النواة."""
    out = json.loads(run(f"""
        import json
        result = {{"raised": False}}
        try:
            from civilization.core.civilization_engine import CivilizationEngine
            CivilizationEngine()
        except PermissionError:
            result["raised"] = True
        print(json.dumps(result))
    """))
    assert out["raised"] is True


def test_main_save_dna_report_refuses_kernel_write(tmp_path):
    """منفذ main.py سلوكياً (كان موصولاً بالحارس بلا تغطية سلوكية — حد معلن
    في 0092): حفظ تقرير DNA داخل شجرة النواة يُرفض ولا يمس المحتوى، والوجهة
    السليمة خارج الشجرة تُكتب فعلاً."""
    out = json.loads(run(f"""
        import json, os
        from types import SimpleNamespace
        from main import save_dna_report
        probe = {str(PROBE)!r}
        dna = SimpleNamespace(to_dict=lambda: {{"name": "x"}})
        result = {{"raised": False, "message_ok": False, "exists": False}}
        try:
            save_dna_report(dna, probe)
        except PermissionError as e:
            result["raised"] = True
            result["message_ok"] = "المادة 16" in str(e)
        result["exists"] = os.path.exists(probe)
        ok_target = {str(tmp_path / 'dna.json')!r}
        save_dna_report(dna, ok_target)
        result["written"] = json.load(open(ok_target))
        print(json.dumps(result))
    """))
    assert out["raised"] is True and out["message_ok"] is True
    assert out["exists"] is False
    assert out["written"] == {"name": "x"}
