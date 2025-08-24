# foundry/actions/ast_insertion_actions.py
"""
Contains actions that surgically add new, complete code constructs to a file.
These tools are for inserting functions, methods, and imports without
overwriting existing code.
"""
import ast
import logging
from typing import List
from pathlib import Path

from src.services import VectorContextService, CodeIntelligenceService

logger = logging.getLogger(__name__)


async def add_class_to_file(path: str, class_code: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Parses a Python file, adds a new class to it, and writes the result back.
    If a class with the same name exists, it will be replaced.
    """
    logger.info(f"Attempting to add class to file: {path}")
    path_obj = Path(path)
    try:
        if not path_obj.exists():
            logger.info(f"File {path} not found. Creating it with the provided class.")
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(class_code + '\n', encoding='utf-8')
            await vector_context_service.reindex_file(path_obj, class_code)
            await code_intelligence_service.update_index_for_file(path_obj, class_code)
            return f"Successfully created new file {path} with the provided class."

        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        new_class_tree = ast.parse(class_code)

        new_class_def = next((node for node in new_class_tree.body if isinstance(node, ast.ClassDef)), None)

        if not new_class_def:
            return "Error: The provided `class_code` did not contain a valid class definition."

        class_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and existing_node.name == new_class_def.name:
                tree.body[i] = new_class_def
                class_replaced = True
                break

        if not class_replaced:
            tree.body.append(new_class_def)

        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        status = "replaced" if class_replaced else "added"
        return f"Successfully {status} class '{new_class_def.name}' in '{path}'."

    except SyntaxError as e:
        return f"Error: Syntax error in '{path}' or `class_code`. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while adding class: {e}"


async def add_function_to_file(path: str, function_code: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Parses a Python file, adds a new function to it, and writes the result back.
    """
    logger.info(f"Attempting to add function to file: {path}")
    path_obj = Path(path)
    try:
        if not path_obj.exists():
            logger.info(f"File {path} not found. Creating it with the provided function.")
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(function_code + '\n', encoding='utf-8')
            await vector_context_service.reindex_file(path_obj, function_code)
            await code_intelligence_service.update_index_for_file(path_obj, function_code)
            return f"Successfully created new file {path} with the provided function."

        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        new_function_tree = ast.parse(function_code)

        new_function_def = next((node for node in new_function_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)

        if not new_function_def:
            return "Error: The provided `function_code` did not contain a valid function definition."

        function_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and existing_node.name == new_function_def.name:
                tree.body[i] = new_function_def
                function_replaced = True
                break

        if not function_replaced:
            tree.body.append(new_function_def)

        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        status = "replaced" if function_replaced else "added"
        return f"Successfully {status} function '{new_function_def.name}' in '{path}'."
    except SyntaxError as e:
        return f"Error: Syntax error in '{path}' or `function_code`. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while adding function: {e}"


async def add_method_to_class(path: str, class_name: str, name: str, args: list, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService, is_async: bool = False) -> str:
    """
    Adds an empty method to a class in a given file.
    """
    logger.info(f"Attempting to add method '{name}' to class '{class_name}' in file '{path}'.")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        class_node = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name), None)

        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        arguments = ast.arguments(args=[ast.arg(arg=arg_name) for arg_name in args], posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[])
        method_body = [ast.Pass()]

        new_method = ast.AsyncFunctionDef(name=name, args=arguments, body=method_body, decorator_list=[]) if is_async else ast.FunctionDef(name=name, args=arguments, body=method_body, decorator_list=[])

        if len(class_node.body) == 1 and isinstance(class_node.body[0], ast.Pass):
            class_node.body = []

        class_node.body.append(new_method)
        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully added method '{name}' to class '{class_name}' in '{path}'."
    except SyntaxError as e:
        return f"Error: The file at '{path}' contains a syntax error. Line {e.lineno}, Column {e.offset}: {e.msg}"
    except Exception as e:
        return f"An unexpected error occurred while adding method: {e}"


async def add_import(path: str, module: str, names: List[str] = [], vector_context_service: VectorContextService = None, code_intelligence_service: CodeIntelligenceService = None) -> str:
    """
    Adds an import statement to a Python file if it doesn't already exist.
    """
    logger.info(f"Attempting to add import for '{module}' to file '{path}'.")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)

        # Check for existing imports
        for node in tree.body:
            if isinstance(node, ast.Import) and not names and any(alias.name == module for alias in node.names):
                return f"Import 'import {module}' already exists in '{path}'."
            elif isinstance(node, ast.ImportFrom) and names and node.module == module and set(names).issubset({alias.name for alias in node.names}):
                return f"Import 'from {module} import {', '.join(names)}' already satisfied in '{path}'."

        import_node = ast.ImportFrom(module=module, names=[ast.alias(name=n) for n in names], level=0) if names else ast.Import(names=[ast.alias(name=module)])
        import_str = f"from {module} import {', '.join(names)}" if names else f"import {module}"

        insert_pos = 0
        for i, node in enumerate(tree.body):
            if not isinstance(node, (ast.Import, ast.ImportFrom)) and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Str)):
                break
            insert_pos = i + 1

        tree.body.insert(insert_pos, import_node)
        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully added import '{import_str}' to '{path}'."
    except SyntaxError as e:
        return f"Error: Syntax error in '{path}'. Line {e.lineno}, Column {e.offset}: {e.msg}"
    except Exception as e:
        return f"An unexpected error occurred while adding import: {e}"