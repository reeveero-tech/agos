"""RIE Infrastructure - Git operations, file system operations."""
import os
import shutil
import subprocess
import tempfile
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

# R-F-006: relative imports — rie works as `rie`, `agos.rie` and under any sys.path root
from ..domain import FileNode, Repository


class GitFetcher:
    """Fetches repositories from git."""
    
    def fetch(self, url: str, branch: str = "main", depth: int = 1) -> str:
        """Clone repository and return local path — hardened (R-W2-005).

        Delegates to the kernel's ``clone_safety`` (single source, same as the kernel
        provider): URL allowlist, timeout, size/file caps, escaping-symlink rejection,
        guaranteed temp cleanup on failure, and one retry with the repository's default
        branch when ``branch`` does not exist. The old body was a bare ``git clone``
        with no timeout and a temp dir that leaked on any failure.
        """
        try:
            from agos.kernel import clone_safety
        except ImportError:
            import clone_safety
        return clone_safety.clone(url, branch=branch, depth=depth)
    
    def get_metadata(self, repo_path: str) -> Dict[str, Any]:
        """Get repository metadata."""
        # Get remote URL
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True
        )
        url = result.stdout.strip()
        
        # Get branch
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        branch = result.stdout.strip()
        
        # Get commit
        result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        commit = result.stdout.strip()
        
        # Get name and owner
        name = os.path.basename(url).replace(".git", "")
        parts = url.replace(".git", "").split("/")
        owner = parts[-2] if len(parts) >= 2 else ""
        
        return {
            "url": url,
            "name": name,
            "owner": owner,
            "branch": branch,
            "commit": commit
        }
    
    def cleanup(self, repo_path: str) -> None:
        """Clean up cloned repository."""
        parent = os.path.dirname(repo_path)
        if os.path.exists(parent):
            shutil.rmtree(parent, ignore_errors=True)


class FileSystemReader:
    """Reads files from filesystem."""
    
    def __init__(self, max_file_size: int = 1024 * 1024):  # 1MB
        self.max_file_size = max_file_size
    
    def read_repository(self, repo_path: str) -> List[FileNode]:
        """Read all files in repository."""
        files = []
        
        # R-W2-004: the kernel's single source decides which hidden paths are relevant.
        from ..detectors import _stack_detection
        _is_relevant_hidden = _stack_detection().is_relevant_hidden
        
        for dirpath, dirnames, filenames in os.walk(repo_path):
            # Skip .git itself — exact path part, so .github (CI config, R-W2-004) survives.
            if any(part == ".git" for part in PurePosixPath(dirpath).parts):
                continue
            
            rel_dir = os.path.relpath(dirpath, repo_path)
            
            # Directories — relevant hidden ones (.github, .circleci, .gitlab) are project
            # data: CI configuration (R-W2-004). Everything else hidden stays skipped.
            # Prune (not just skip): a skipped hidden dir must not contribute the
            # non-hidden files inside it (".idea/workspace.xml" would sneak in).
            dirnames[:] = [d for d in dirnames
                           if not (d.startswith(".") and not _is_relevant_hidden(d))]
            for dirname in dirnames:
                dir_path = os.path.join(rel_dir, dirname) if rel_dir != "." else dirname
                files.append(FileNode(path=dir_path, is_dir=True))
            
            # Files
            for filename in filenames:
                if filename.startswith(".") and not _is_relevant_hidden(
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
                    content = None
                    
                    if size < self.max_file_size:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    
                    ext = os.path.splitext(filename)[1]
                    
                    files.append(FileNode(
                        path=file_path,
                        is_dir=False,
                        size=size,
                        content=content,
                        extension=ext
                    ))
                except:
                    pass
        
        return files


class RepositoryNormalizer:
    """Normalizes repositories to universal format."""
    
    def __init__(self, fetcher: GitFetcher, reader: FileSystemReader):
        self.fetcher = fetcher
        self.reader = reader
    
    def normalize(self, url: str, branch: str = "main",
                  repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Normalize a repository.

        ``repo_path`` (R-W2-005): a path already fetched by the caller — used as is and
        the caller owns its cleanup. Without it the normalizer fetches its own copy and
        cleans it up in a ``finally`` — the previous body leaked that temp dir on every
        call (the pipeline fetched one copy and never removed the normalizer's second).

        R-W2-006 (ADR-0005): الخط الواحد — القراءة والفهرسة عبر الخدمة
        المشتركة نفسها (سياسة القارئ القديمة R-W2-004 هي سياسة النواة)،
        و``normalized`` يُبنى من حقائقها؛ البنية (جلب/تنظيف) كما هي.
        """
        from agos_kernel.capabilities.analysis_service import (
            KERNEL_SCAN_POLICY, get_analysis_service)

        # Fetch (unless the caller already did) — الملكية: ما جلبه المنظّم
        # بنفسه يُنظّفه؛ والمسار المحقون ملك مستدعيه لا يُمس
        own_path = repo_path is None
        if repo_path is None:
            repo_path = self.fetcher.fetch(url, branch)
        
        try:
            # Get metadata — من المستودع المجلوب كما في القديم
            metadata = self.fetcher.get_metadata(repo_path)
            
            # القراءة والفهرسة — الخط الواحد (الخدمة المشتركة)
            shared = get_analysis_service().analyze_path(
                repo_path, policy=KERNEL_SCAN_POLICY)
            
            directories = sorted(f.path for f in shared.files if f.is_dir)
            file_data = {
                f.path: {
                    "size": f.size_bytes,
                    "extension": f.extension,
                    "has_content": f.path in shared.contents
                }
                for f in shared.files if not f.is_dir
            }
            # R-W2-001: keep the contents of dependency manifests (only those — small and
            # few) so detectors can read them via DetectorContext.get_file_content, which
            # reads metadata["_content"]. R-W2-003: code files are kept too — the
            # LanguageDetector can weigh languages by lines instead of falling back to
            # file counts. No extra disk reads (من محتوى المسح الواحد).
            from ..detectors import _stack_detection
            sd = _stack_detection()
            is_manifest = sd.is_manifest
            is_code_ext = {ext for exts in sd.LANGUAGE_EXTENSIONS.values() for ext in exts}
            manifest_content = {
                f.path: shared.contents[f.path]
                for f in shared.files
                if not f.is_dir and f.path in shared.contents
                and (is_manifest(f.path) or f.extension in is_code_ext)
            }
            
            return {
                "_content": manifest_content,
                "url": metadata["url"],
                "name": metadata["name"],
                "owner": metadata["owner"],
                "branch": metadata["branch"],
                "commit": metadata["commit"],
                "directories": directories,
                "files": file_data,
                "total_files": len([f for f in shared.files if not f.is_dir]),
                "total_directories": len(directories)
            }
        finally:
            # التنظيف لما جلبه المنظّم فقط — المسار المحقون ملك مستدعيه
            if own_path:
                self.fetcher.cleanup(repo_path)
