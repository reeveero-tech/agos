"""File Operations Skills."""
import os
import shutil
from typing import Any, Dict, List, Optional
from ..base import Skill


class ReadFileSkill(Skill):
    """Read a file."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("ReadFile", "Read file contents")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Read file."""
        path = input_data.get("path", "")
        if not os.path.exists(path):
            return {"success": False, "error": "File not found"}
        
        try:
            with open(path, "r") as f:
                content = f.read()
            return {"success": True, "path": path, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}


class WriteFileSkill(Skill):
    """Write a file."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("WriteFile", "Write content to file")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Write file."""
        path = input_data.get("path", "")
        content = input_data.get("content", "")
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}


class DeleteFileSkill(Skill):
    """Delete a file."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("DeleteFile", "Delete a file or directory")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete file."""
        path = input_data.get("path", "")
        
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}


class MoveFileSkill(Skill):
    """Move a file."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("MoveFile", "Move a file to new location")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Move file."""
        src = input_data.get("src", "")
        dst = input_data.get("dst", "")
        
        try:
            shutil.move(src, dst)
            return {"success": True, "src": src, "dst": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CopyFileSkill(Skill):
    """Copy a file."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("CopyFile", "Copy a file to new location")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Copy file."""
        src = input_data.get("src", "")
        dst = input_data.get("dst", "")
        
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return {"success": True, "src": src, "dst": dst}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SearchFilesSkill(Skill):
    """Search for files."""
    
    def __init__(self):
        """Initialize skill."""
        super().__init__("SearchFiles", "Search for files matching pattern")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Search files."""
        root = input_data.get("root", ".")
        pattern = input_data.get("pattern", "*")
        
        matches = []
        for root_dir, dirs, files in os.walk(root):
            for f in files:
                if pattern in f or pattern == "*":
                    matches.append(os.path.join(root_dir, f))
        
        return {"success": True, "matches": matches[:100]}


class ReadDocumentationSkill(Skill):
    """Read documentation files (README, docs/) from a repository."""

    def __init__(self):
        """Initialize skill."""
        super().__init__("ReadDocumentation", "Read documentation files")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Read documentation."""
        root = input_data.get("root", ".")
        doc_names = ("readme", "changelog", "contributing", "license")
        docs = []
        for root_dir, dirs, files in os.walk(root):
            for f in files:
                lower = f.lower()
                if lower.startswith(doc_names) or root_dir.lower().endswith("docs"):
                    docs.append(os.path.join(root_dir, f))
        return {"success": True, "documents": docs[:100]}


class ReadConfigurationSkill(Skill):
    """Read configuration files (json/yaml/toml/ini) from a repository."""

    def __init__(self):
        """Initialize skill."""
        super().__init__("ReadConfiguration", "Read configuration files")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Read configuration files."""
        root = input_data.get("root", ".")
        config_exts = (".json", ".yaml", ".yml", ".toml", ".ini", ".cfg")
        configs = []
        for root_dir, dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith(config_exts):
                    configs.append(os.path.join(root_dir, f))
        return {"success": True, "configs": configs[:100]}


# Registry of file skills
FILE_SKILLS = {
    "read": ReadFileSkill,
    "write": WriteFileSkill,
    "delete": DeleteFileSkill,
    "move": MoveFileSkill,
    "copy": CopyFileSkill,
    "search": SearchFilesSkill,
    "read_documentation": ReadDocumentationSkill,
    "read_configuration": ReadConfigurationSkill,
}


def get_skill(name: str) -> Skill:
    """Get a file skill."""
    skill_class = FILE_SKILLS.get(name)
    if not skill_class:
        raise ValueError(f"Unknown file skill: {name}")
    return skill_class()