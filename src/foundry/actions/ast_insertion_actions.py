# foundry/actions/ast_insertion_actions.py
"""
Contains actions that surgically add new, complete code constructs to a file.
These tools are for inserting functions, methods, and imports without
overwriting existing code.
"""
import ast
import logging
from typing import List

logger = logging.getLogger(__name__)


def add_class_to_file(path: str, class_code: str) -> str:
    """
    Parses a Python file, adds a new class to it, and writes the result back.
    If a class with the same name exists, it will be replaced.
    """
    logger.info(f"Attempting to add class to file: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logger.info(f"File {path} not found. Creating it with the provided class.")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(class_code + '\n')
        return f"Successfully created new file {path} with the provided class."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)
        new_class_tree = ast.parse(class_code)

        new_class_def = None
        for node in new_class_tree.body:
            if isinstance(node, ast.ClassDef):
                new_class_def = node
                break

        if not new_class_def:
            return "Error: The provided `class_code` did not contain a valid class definition."

        # Check if a class or function with the same name already exists and replace it.
        class_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node, (ast.ClassDef, ast.FunctionDef,
                                          ast.AsyncFunctionDef)) and existing_node.name == new_class_def.name:
                tree.body[i] = new_class_def
                class_replaced = True
                break

        if not class_replaced:
            tree.body.append(new_class_def)

        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        status = "replaced" if class_replaced else "added"
        success_message = f"Successfully {status} class '{new_class_def.name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in the file '{path}' or in the provided `class_code`. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding class: {e}"
        logger.exception(error_message)
        return error_message


def add_function_to_file(path: str, function_code: str) -> str:
    """
    Parses a Python file, adds a new function to it, and writes the result back.
    This is a non-destructive way to add code.
    """
    logger.info(f"Attempting to add function to file: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        # If the file doesn't exist, we can treat this as a write_file operation.
        logger.info(f"File {path} not found. Creating it with the provided function.")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(function_code + '\n')
        return f"Successfully created new file {path} with the provided function."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)
        new_function_tree = ast.parse(function_code)

        new_function_def = None
        for node in new_function_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                new_function_def = node
                break

        if not new_function_def:
            return "Error: The provided `function_code` did not contain a valid function definition."

        # Check if a function with the same name already exists and replace it.
        function_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node,
                          (ast.FunctionDef, ast.AsyncFunctionDef)) and existing_node.name == new_function_def.name:
                tree.body[i] = new_function_def
                function_replaced = True
                break

        if not function_replaced:
            tree.body.append(new_function_def)

        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        status = "replaced" if function_replaced else "added"
        success_message = f"Successfully {status} function '{new_function_def.name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in the file '{path}' or in the provided `function_code`. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding function: {e}"
        logger.exception(error_message)
        return error_message


def add_method_to_class(path: str, class_name: str, name: str, args: list, is_async: bool = False) -> str:
    """
    Adds an empty method to a class in a given file.

    Args:
        path: The path to the Python file.
        class_name: The name of the class to modify.
        name: The name of the new method.
        args: The arguments for the new method.
        is_async: If True, creates an 'async def' method.

    Returns:
        A string indicating success or failure.
    """
    logger.info(f"Attempting to add method '{name}' to class '{class_name}' in file '{path}'.")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)
        class_node = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break

        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        arguments = ast.arguments(
            args=[ast.arg(arg=arg_name) for arg_name in args],
            posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        )
        method_body = [ast.Pass()]

        if is_async:
            new_method = ast.AsyncFunctionDef(
                name=name, args=arguments, body=method_body, decorator_list=[]
            )
        else:
            new_method = ast.FunctionDef(
                name=name, args=arguments, body=method_body, decorator_list=[]
            )

        if len(class_node.body) == 1 and isinstance(class_node.body[0], ast.Pass):
            class_node.body = []

        class_node.body.append(new_method)

        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully added method '{name}' to class '{class_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: The file at '{path}' contains a syntax error and could not be parsed. Line {e.lineno}, Column {e.offset}: {e.msg}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding method: {e}"
        logger.exception(error_message)
        return error_message


def add_import(path: str, module: str, names: List[str] = []) -> str:
    """
    Adds an import statement to a Python file if it doesn't already exist.

    Args:
        path: The path to the Python file.
        module: The module to import (e.g., 'os').
        names: A list of specific names to import from the module (for 'from ... import ...').

    Returns:
        A string indicating success, that it already existed, or failure.
    """
    logger.info(f"Attempting to add import for '{module}' to file '{path}'.")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)

        # Check for existing imports to avoid duplicates
        for node in tree.body:
            if isinstance(node, ast.Import) and not names:
                if any(alias.name == module for alias in node.names):
                    return f"Import 'import {module}' already exists in '{path}'."
            elif isinstance(node, ast.ImportFrom) and names and node.module == module:
                existing_names = {alias.name for alias in node.names}
                if set(names).issubset(existing_names):
                    return f"Import 'from {module} import {', '.join(names)}' already satisfied in '{path}'."

        # Create the new import node
        if names:
            import_node = ast.ImportFrom(module=module, names=[ast.alias(name=n) for n in names], level=0)
            import_str = f"from {module} import {', '.join(names)}"
        else:
            import_node = ast.Import(names=[ast.alias(name=module)])
            import_str = f"import {module}"

        # Find the first non-docstring/import line to insert the new import
        insert_pos = 0
        for i, node in enumerate(tree.body):
            if not isinstance(node, (ast.Import, ast.ImportFrom)) and \
                    not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Str)):
                break
            insert_pos = i + 1

        tree.body.insert(insert_pos, import_node)

        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully added import '{import_str}' to '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: The file at '{path}' contains a syntax error and could not be parsed. Line {e.lineno}, Column {e.offset}: {e.msg}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding import: {e}"
        logger.exception(error_message)
        return error_message