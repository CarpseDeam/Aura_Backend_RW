# src/foundry/actions/code_intelligence_actions.py
import logging
import ast
from typing import List
from src.services.code_intelligence_service import CodeIntelligenceService
from src.core.managers import ProjectManager

logger = logging.getLogger(__name__)


def find_definition(code_intelligence_service: CodeIntelligenceService, symbol_name: str) -> str:
    """
    Finds the definition of a function or class using the code intelligence index.
    """
    if not code_intelligence_service:
        return "Error: Code Intelligence Service is not available."

    definitions = code_intelligence_service.find_symbol_definition(symbol_name)

    if not definitions:
        return f"Symbol '{symbol_name}' not found in the project index."

    response_parts = [f"Found {len(definitions)} definition(s) for '{symbol_name}':"]
    for symbol in definitions:
        part = f"- Type: {symbol.node_type}, File: {symbol.file_path}, Line: {symbol.line_number}"
        if symbol.parent_class:
            part += f" (in class {symbol.parent_class})"
        response_parts.append(part)

    return "\n".join(response_parts)


def find_references(code_intelligence_service: CodeIntelligenceService, symbol_name: str) -> str:
    """
    Finds all references (i.e., usages) of a function or class.
    """
    if not code_intelligence_service:
        return "Error: Code Intelligence Service is not available."

    references = code_intelligence_service.find_references(symbol_name)

    if not references:
        return f"No references to '{symbol_name}' were found in the project index."

    response_parts = [f"Found {len(references)} reference(s) to '{symbol_name}':"]
    for symbol in references:
        part = f"- In {symbol.node_type} '{symbol.name}' at File: {symbol.file_path}, Line: {symbol.line_number}"
        response_parts.append(part)

    return "\n".join(response_parts)


def get_dependencies(code_intelligence_service: CodeIntelligenceService, symbol_name: str) -> str:
    """
    Lists all functions and methods that a given symbol calls.
    """
    if not code_intelligence_service:
        return "Error: Code Intelligence Service is not available."

    definitions = code_intelligence_service.find_symbol_definition(symbol_name)
    if not definitions:
        return f"Symbol '{symbol_name}' not found in the project index."

    # In case of multiple definitions, we'll check the first one.
    symbol = definitions[0]
    if not symbol.calls:
        return f"Symbol '{symbol_name}' does not appear to call any other indexed functions or methods."

    response_parts = [f"Symbol '{symbol_name}' in '{symbol.file_path}' calls the following symbols:"]
    for call in sorted(list(symbol.calls)):
        response_parts.append(f"- {call}")
    return "\n".join(response_parts)


class RenameTransformer(ast.NodeTransformer):
    """
    An AST NodeTransformer to safely rename variables, functions, and classes.
    """
    def __init__(self, old_name, new_name):
        self.old_name = old_name
        self.new_name = new_name

    def visit_Name(self, node):
        if node.id == self.old_name:
            node.id = self.new_name
        return node

    def visit_FunctionDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        if node.arg == self.old_name:
            node.arg = self.new_name
        return node


def rename_symbol(project_manager: ProjectManager, code_intelligence_service: CodeIntelligenceService, old_name: str,
                  new_name: str) -> str:
    """
    Performs a project-wide safe rename of a symbol and its usages.
    """
    if not code_intelligence_service:
        return "Error: Code Intelligence Service is not available."

    definitions = code_intelligence_service.find_symbol_definition(old_name)
    if not definitions:
        return f"Error: Cannot rename. Symbol '{old_name}' not found in the project index."

    references = code_intelligence_service.find_references(old_name)

    # Combine all files that need modification (where the symbol is defined or referenced)
    files_to_modify = {s.file_path for s in definitions + references}

    for rel_path_str in files_to_modify:
        if not project_manager.active_project_path:
            return "Error: No active project to perform rename in."
        full_path = project_manager.active_project_path / rel_path_str
        try:
            content = full_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            transformer = RenameTransformer(old_name, new_name)
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)
            new_content = ast.unparse(new_tree)
            full_path.write_text(new_content, encoding='utf-8')
            logger.info(f"Successfully applied rename in {rel_path_str}")
        except Exception as e:
            return f"Failed to rename in file {rel_path_str}: {e}"

    return f"Successfully renamed '{old_name}' to '{new_name}' across {len(files_to_modify)} files."