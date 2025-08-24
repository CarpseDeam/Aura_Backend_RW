# src/services/code_intelligence_service.py
import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CodeSymbol:
    """Represents a defined symbol (class, function, method) in the codebase."""
    name: str
    file_path: str
    line_number: int
    node_type: str  # 'class', 'function', 'method'
    parent_class: Optional[str] = None
    calls: Set[str] = field(default_factory=set)  # Names of functions/methods this symbol calls


class SymbolVisitor(ast.NodeVisitor):
    """An AST visitor to find symbol definitions and their internal calls."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[CodeSymbol] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        self.symbols.append(CodeSymbol(
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            node_type='class'
        ))
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        node_type = 'method' if self.current_class else 'function'
        symbol = CodeSymbol(
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            node_type=node_type,
            parent_class=self.current_class
        )
        # Find calls within this function
        call_visitor = CallVisitor()
        call_visitor.visit(node)
        symbol.calls = call_visitor.calls
        self.symbols.append(symbol)
        # We don't call generic_visit here to avoid recursion into nested functions for now

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node)


class CallVisitor(ast.NodeVisitor):
    """A focused visitor to find function/method calls within a specific node."""

    def __init__(self):
        self.calls: Set[str] = set()

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # This captures method calls like `self.some_method()` or `other.func()`
            self.calls.add(node.func.attr)
        self.generic_visit(node)


class CodeIntelligenceService:
    """
    Maintains an in-memory model of the project's code structure (AST-based symbol table).
    """

    def __init__(self):
        self.project_root: Optional[Path] = None
        # Main symbol table: {symbol_name: [CodeSymbol, ...]} (list for overloads/same names)
        self._symbol_definitions: Dict[str, List[CodeSymbol]] = {}
        # Reverse index for quick file-based lookups and updates
        self._file_to_symbols: Dict[str, List[str]] = {}
        logger.info("CodeIntelligenceService initialized.")

    def load_for_project(self, project_path: Path):
        """Loads the service for a specific project, clearing any previous state."""
        self.project_root = project_path
        self._symbol_definitions.clear()
        self._file_to_symbols.clear()
        logger.info(f"Code Intelligence Service loaded for project: {project_path.name}")

    async def build_index_for_project(self):
        """Scans the entire project and builds the symbol index."""
        if not self.project_root:
            logger.error("Cannot build index: project_root is not set.")
            return

        logger.info("Building project-wide code intelligence index...")
        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', '.rag_db', 'node_modules'}
        py_files = [p for p in self.project_root.rglob("*.py") if
                    not any(excluded in p.parts for excluded in ignore_dirs)]

        for file_path in py_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                await self.update_index_for_file(file_path, content)
            except Exception as e:
                logger.warning(f"Could not process file {file_path} for code index: {e}")

        logger.info(f"Code intelligence index built. Found {len(self._symbol_definitions)} unique symbol names.")

    async def update_index_for_file(self, file_path: Path, content: str):
        """Updates the index for a single file."""
        if not self.project_root: return
        relative_path_str = str(file_path.relative_to(self.project_root))

        if relative_path_str in self._file_to_symbols:
            for symbol_name in self._file_to_symbols[relative_path_str]:
                if symbol_name in self._symbol_definitions:
                    self._symbol_definitions[symbol_name] = [
                        s for s in self._symbol_definitions[symbol_name] if s.file_path != relative_path_str
                    ]
                    if not self._symbol_definitions[symbol_name]:
                        del self._symbol_definitions[symbol_name]
            del self._file_to_symbols[relative_path_str]

        try:
            tree = ast.parse(content)
            visitor = SymbolVisitor(relative_path_str)
            visitor.visit(tree)

            new_symbol_names = []
            for symbol in visitor.symbols:
                if symbol.name not in self._symbol_definitions: self._symbol_definitions[symbol.name] = []
                self._symbol_definitions[symbol.name].append(symbol)
                new_symbol_names.append(symbol.name)

            if new_symbol_names: self._file_to_symbols[relative_path_str] = new_symbol_names
            logger.debug(f"Updated index for '{relative_path_str}', found {len(new_symbol_names)} symbols.")
        except (SyntaxError, TypeError) as e:
            logger.warning(f"Syntax error in {relative_path_str}, cannot update code index: {e}")

    def find_symbol_definition(self, symbol_name: str) -> List[CodeSymbol]:
        """Finds the definition(s) of a symbol by name."""
        return self._symbol_definitions.get(symbol_name, [])

    def find_references(self, symbol_name: str) -> List[CodeSymbol]:
        """Finds all symbols that call the given symbol_name."""
        references = []
        for symbols in self._symbol_definitions.values():
            for symbol in symbols:
                if symbol_name in symbol.calls:
                    references.append(symbol)
        return references