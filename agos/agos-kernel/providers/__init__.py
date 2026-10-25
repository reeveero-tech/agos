"""Local Repository Provider."""
import os
import subprocess
import tempfile
from pathlib import PurePosixPath
from typing import Generator, Optional

from contracts import FileNode, RepositoryMetadata, RepositorySnapshot
from interfaces import IProvider, SkillInput, SkillOutput


class CloneRepositoryInput(SkillInput):
    """Input for CloneRepository skill.

    ``branch=None``: لا يُمرر ``--branch`` فيختار git الفرع الافتراضي بنفسه
    (مقبول تصريحاً — التنفيذ يدعمه؛ الشريحة 0100). ``require_metadata=False``:
    استنساخ بلا ميتاداتا — ي preserved المدخلات المقبولة للمستهلكين الذين لا
    يقرؤون الميتاداتا أصلاً (مستودع فارغ بلا commits له origin لكن بلا HEAD
    فقراءة الميتاداتا ترفضه — الاستنساخ وحده لا يرفضه).
    """
    def __init__(self, url: str, branch: Optional[str] = "main",
                 require_metadata: bool = True):
        self.url = url
        self.branch = branch
        self.require_metadata = require_metadata


class CloneRepositoryOutput(SkillOutput):
    """Output from CloneRepository skill."""
    def __init__(self, path: str, metadata: RepositoryMetadata):
        self.path = path
        self.metadata = metadata


class ReadRepositoryInput(SkillInput):
    """Input for ReadRepository skill."""
    def __init__(self, path: str):
        self.path = path


class ReadRepositoryOutput(SkillOutput):
    """Output from ReadRepository skill."""
    def __init__(self, snapshot: RepositorySnapshot):
        self.snapshot = snapshot


class WalkRepositoryInput(SkillInput):
    """Input for WalkRepository skill (المادة 4 — الشريحة 0100): مسح ملفات
    جذر مستودع بلا ميتاداتا — يحفظ المدخلات المقبولة للمسارات المحلية
    (مستودع بلا origin يبقى مقروءاً — قراءة ReadRepository تشترطها)."""
    def __init__(self, path: str):
        self.path = path


class WalkRepositoryOutput(SkillOutput):
    """Output from WalkRepository skill: عقد ملفات المستودع كما هي (لا ميتاداتا)."""
    def __init__(self, files: list):
        self.files = files


class LocalRepositoryProvider(IProvider):
    """
    Provider for local filesystem repository operations.
    Stateless, replaceable, no business logic.
    """
    
    @property
    def name(self) -> str:
        return "LocalRepositoryProvider"
    
    def supports_skill(self, skill_name: str) -> bool:
        return skill_name in ["CloneRepository", "ReadRepository",
                              "WalkRepository"]
    
    def execute(self, skill_name: str, input_data: SkillInput) -> SkillOutput:
        if skill_name == "CloneRepository":
            return self._clone(input_data)
        elif skill_name == "ReadRepository":
            return self._read(input_data)
        elif skill_name == "WalkRepository":
            return self._walk(input_data)
        else:
            raise ValueError(f"Unknown skill: {skill_name}")
    
    def Clone(self, url: str, branch: str = "main") -> str:
        """Clone a git repository — hardened (R-W2-005).

        Delegates to the kernel's ``clone_safety`` (single source): URL allowlist,
        timeout, size/file caps, escaping-symlink rejection, guaranteed temp cleanup on
        failure, and one retry with the repository's default branch when the requested
        branch does not exist (a ``master`` default no longer fails because "main" was
        assumed). The returned path is owned by the caller on success.
        """
        from clone_safety import clone
        return clone(url, branch)
    
    def Open(self, path: str) -> str:
        """Open a repository."""
        if not os.path.isdir(path):
            raise ValueError(f"Not a directory: {path}")
        if not os.path.isdir(os.path.join(path, ".git")):
            raise ValueError(f"Not a git repository: {path}")
        return os.path.abspath(path)
    
    def Read(self, path: str) -> RepositorySnapshot:
        """Read an entire repository."""
        repo_path = self.Open(path)
        metadata = self.Metadata(repo_path)
        files = list(self._walk_files(repo_path))
        return RepositorySnapshot(metadata=metadata, files=files, root_path=repo_path)
    
    def Walk(self, path: str) -> Generator[FileNode, None, None]:
        """Walk through files."""
        repo_path = self.Open(path)
        yield from self._walk_files(repo_path)
    
    def Exists(self, path: str) -> bool:
        """Check if repository exists."""
        return os.path.isdir(os.path.join(path, ".git"))
    
    def Metadata(self, path: str) -> RepositoryMetadata:
        """Get repository metadata."""
        repo_path = self.Open(path)
        
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        url = result.stdout.strip()
        
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        branch = result.stdout.strip()
        
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        commit = result.stdout.strip()
        
        name = os.path.basename(url).replace(".git", "")
        parts = url.replace(".git", "").split("/")
        owner = parts[-2] if len(parts) >= 2 else ""
        
        return RepositoryMetadata(
            url=url, name=name, owner=owner,
            branch=branch, commit=commit
        )
    
    def _clone(self, input_data: CloneRepositoryInput) -> CloneRepositoryOutput:
        path = self.Clone(input_data.url, input_data.branch)
        metadata = None
        if getattr(input_data, "require_metadata", True):
            try:
                metadata = self.Metadata(path)
            except BaseException:
                # فشل الميتاداتا بعد نجاح الاستنساخ وقبل التسليم: النسخة ملكنا
                # بعد (منتجها نحن ولم تُسلَّم) — تنظيفها مسؤوليتنا (لا تسرب)
                # ثم إعادة رفع السبب كما هو. الحذف يشمل الجذر وحده؛ والوالد
                # الفارغ يُزال فقط إن كان فارغاً (بنية temp التي أنشأها
                # المنتج نفسه — dest=None دائماً في هذا العقد).
                import shutil
                shutil.rmtree(path, ignore_errors=True)
                try:
                    os.rmdir(os.path.dirname(path))
                except OSError:
                    pass
                raise
        return CloneRepositoryOutput(path=path, metadata=metadata)
    
    def _read(self, input_data: ReadRepositoryInput) -> ReadRepositoryOutput:
        snapshot = self.Read(input_data.path)
        return ReadRepositoryOutput(snapshot=snapshot)
    
    def _walk(self, input_data: WalkRepositoryInput) -> WalkRepositoryOutput:
        # المادة 4 (الشريحة 0100): المسح بعقد مهارة معلن — لا استدعاء مباشر
        # لطريقة الصنف من المستهلكين؛ يحفظ المدخلات المقبولة (بلا ميتاداتا
        # فلا اشتراط origin — المستودع المحلي بلا remote يبقى مقروءاً)
        return WalkRepositoryOutput(files=list(self.Walk(input_data.path)))
    
    def _walk_files(self, root: str) -> Generator[FileNode, None, None]:
        """Walk through files in a directory."""
        # R-W2-004: relevant hidden files/dirs are part of the project — .github,
        # .gitignore, .env.example, … — everything else hidden (and .git always) is skipped.
        from stack_detection import is_relevant_hidden
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip .git itself — exact path part, so .github (CI config, R-W2-004) survives.
            if any(part == ".git" for part in PurePosixPath(dirpath).parts):
                continue
            
            rel_dir = os.path.relpath(dirpath, root)
            
            # Prune (not just skip): a skipped hidden dir must not contribute the
            # non-hidden files inside it (".idea/workspace.xml" would sneak in).
            dirnames[:] = [d for d in dirnames
                           if not (d.startswith(".") and not is_relevant_hidden(
                               os.path.join(rel_dir, d) if rel_dir != "." else d))]
            for dirname in dirnames:
                dir_path = os.path.join(rel_dir, dirname) if rel_dir != "." else dirname
                yield FileNode(path=dir_path, is_dir=True)
            
            for filename in filenames:
                if filename.startswith(".") and not is_relevant_hidden(
                        os.path.join(rel_dir, filename) if rel_dir != "." else filename):
                    continue
                full_path = os.path.join(dirpath, filename)
                # R-W2-005: a symlinked file may resolve outside the repository root —
                # never read through it (dirs are already not followed by os.walk).
                if os.path.islink(full_path):
                    continue
                file_path = os.path.join(rel_dir, filename) if rel_dir != "." else filename
                
                try:
                    size = os.path.getsize(full_path)
                    if size < 1024 * 1024:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    else:
                        content = None
                except:
                    size = 0
                    content = None
                
                yield FileNode(path=file_path, is_dir=False, size=size, content=content)
