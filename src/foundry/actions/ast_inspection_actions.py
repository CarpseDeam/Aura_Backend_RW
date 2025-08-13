# foundry/actions/ast_inspection_actions.py
"""
Contains actions that read and analyze code using AST without changing it.
These tools are for understanding code structure and content.
"""
import ast
import logging

logger = logging.getLogger(__name__)


def get_generated_code() -> str:
    """Unparses a complete AST module into a Python code string."""
    logger.info("Unparsing the current AST to generate code string.")
    try:
        # This tool is a remnant of an older, AST-based generation pipeline.
        # In the new file-based pipeline, it doesn't have a direct code AST to process.
        # Returning a helpful message in the correct format.
        return f"Generated Code:\n```python\n# This tool is part of the new file-based generation pipeline.\n# Use 'read_file' or 'list_files' to inspect results.\n```"
    except Exception as e:
        return f"An unexpected error occurred while unparsing the AST: {e}"


def list_functions_in_file(path: str) -> str:
    """
    Parses a Python file and returns a list of its top-level function names.

    Args:
        path: The path to the Python file.

    Returns:
        A string listing the function names, or an error message.
    """
    logger.info(f"Attempting to list functions in file: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        error_msg = f"Error: File not found at '{path}'."
        logger.warning(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error reading file at '{path}': {e}"
        logger.exception(error_msg)
        return error_msg

    try:
        tree = ast.parse(content)
        function_names = [
            node.name for node in tree.body
            if isinstance(node, ast.FunctionDef)
        ]

        if not function_names:
            return f"No top-level functions found in '{path}'."

        result_str = f"Functions in '{path}':\n" + "\n".join(f"- {name}" for name in sorted(function_names))
        logger.info(f"Found functions in '{path}': {', '.join(function_names)}")
        return result_str

    except SyntaxError as e:
        error_msg = f"Error: The file at '{path}' contains a syntax error and could not be parsed. Line {e.lineno}, Column {e.offset}: {e.msg}"
        logger.warning(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred while parsing file '{path}': {e}"
        logger.exception(error_msg)
        return error_msg


def get_code_for(path: str, function_name: str) -> str:
    """
    Parses a Python file and returns the full source code for a specific function or class.

    Args:
        path: The path to the Python file.
        function_name: The name of the node to retrieve.

    Returns:
        A formatted string with the node's source code, or an error message.
    """
    logger.info(f"Attempting to get source for node '{function_name}' in file: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == function_name:
                source_code = ast.unparse(node)
                logger.info(f"Successfully extracted source code for '{function_name}'.")
                return f"Source code for '{function_name}' from '{path}':\n```python\n{source_code}\n```"

        not_found_msg = f"Error: Node '{function_name}' not found as a top-level function or class in '{path}'."
        logger.warning(not_found_msg)
        return not_found_msg

    except SyntaxError as e:
        return f"Error: The file at '{path}' contains a syntax error and could not be parsed. Line {e.lineno}, Column {e.offset}: {e.msg}"
    except Exception as e:
        return f"An unexpected error occurred while parsing file '{path}': {e}"