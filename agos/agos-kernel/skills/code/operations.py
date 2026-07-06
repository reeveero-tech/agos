"""Code Analysis Skills (Symbols, AST, Imports)."""
import ast
from typing import Any, Dict, List
from ..base import Skill


class SearchSymbolsSkill(Skill):
    """Search for symbols (functions/classes) in source code."""

    def __init__(self):
        super().__init__("SearchSymbols", "Search for symbols in source code")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        source = input_data.get("source", "")
        query = input_data.get("query", "")
        symbols: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not query or query.lower() in node.name.lower():
                        symbols.append({
                            "name": node.name,
                            "type": type(node).__name__,
                            "line": node.lineno,
                        })
            return {"success": True, "symbols": symbols}
        except SyntaxError as e:
            return {"success": False, "error": str(e), "symbols": []}


class ParseASTSkill(Skill):
    """Parse source code into an AST representation."""

    def __init__(self):
        super().__init__("ParseAST", "Parse source code into an AST")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        source = input_data.get("source", "")
        try:
            tree = ast.parse(source)
            return {"success": True, "dump": ast.dump(tree)}
        except SyntaxError as e:
            return {"success": False, "error": str(e)}


class GenerateASTSkill(Skill):
    """Generate source code from an AST-like structure (round trip helper)."""

    def __init__(self):
        super().__init__("GenerateAST", "Generate source from an AST")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        source = input_data.get("source", "")
        try:
            tree = ast.parse(source)
            generated = ast.unparse(tree)
            return {"success": True, "generated": generated}
        except (SyntaxError, ValueError) as e:
            return {"success": False, "error": str(e)}


class AnalyzeImportsSkill(Skill):
    """Analyze imports used in source code."""

    def __init__(self):
        super().__init__("AnalyzeImports", "Analyze imports in source code")

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        source = input_data.get("source", "")
        imports: List[str] = []
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            return {"success": True, "imports": sorted(set(imports))}
        except SyntaxError as e:
            return {"success": False, "error": str(e), "imports": []}


CODE_SKILLS = {
    "search_symbols": SearchSymbolsSkill,
    "parse_ast": ParseASTSkill,
    "generate_ast": GenerateASTSkill,
    "analyze_imports": AnalyzeImportsSkill,
}


def get_skill(name: str) -> Skill:
    """Get a code skill."""
    skill_class = CODE_SKILLS.get(name)
    if not skill_class:
        raise ValueError(f"Unknown code skill: {name}")
    return skill_class()
