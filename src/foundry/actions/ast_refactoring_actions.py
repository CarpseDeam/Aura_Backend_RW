# foundry/actions/ast_refactoring_actions.py
"""
Contains actions that modify or refactor existing code constructs using AST.
These tools are for targeted changes like renaming symbols or appending
logic to functions.
"""
import ast
import logging
from typing import Optional
from pathlib import Path

from src.services import VectorContextService, CodeIntelligenceService

logger = logging.getLogger(__name__)


async def add_parameter_to_function(path: str, function_name: str, parameter_name: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService, parameter_type: Optional[str] = None, default_value: Optional[str] = None) -> str:
    """
    Adds a new parameter to a function's signature using AST.
    """
    logger.info(f"Adding parameter '{parameter_name}' to function '{function_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."

    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        func_node = next((node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name), None)

        if not func_node:
            return f"Error: Function '{function_name}' not found in '{path}'."

        new_arg = ast.arg(arg=parameter_name, annotation=ast.Name(id=parameter_type, ctx=ast.Load()) if parameter_type else None)

        if any(arg.arg == parameter_name for arg in func_node.args.args) or any(arg.arg == parameter_name for arg in func_node.args.kwonlyargs):
            return f"Error: Parameter '{parameter_name}' already exists in function '{function_name}'."

        if default_value is not None:
            try:
                value_node = ast.Constant(value=ast.literal_eval(default_value))
            except (ValueError, SyntaxError):
                value_node = ast.Name(id=default_value, ctx=ast.Load())
            func_node.args.kwonlyargs.append(new_arg)
            func_node.args.kw_defaults.append(value_node)
        else:
            first_default_idx = len(func_node.args.args) - len(func_node.args.defaults)
            func_node.args.args.insert(first_default_idx, new_arg)

        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully added parameter '{parameter_name}' to function '{function_name}' in '{path}'."

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while adding parameter: {e}"


async def add_attribute_to_init(path: str, class_name: str, attribute_name: str, default_value: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Adds a 'self.attribute = value' line to the __init__ of a class.
    """
    logger.info(f"Adding attribute '{attribute_name}' to class '{class_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        class_node = next((node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name), None)

        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        init_method = next((node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == '__init__'), None)

        if not init_method:
            logger.info(f"__init__ not found in '{class_name}'. Creating a new one.")
            args = ast.arguments(args=[ast.arg(arg='self')], posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[])
            init_method = ast.FunctionDef(name='__init__', args=args, body=[], decorator_list=[], returns=None)
            class_node.body.insert(0, init_method)

        target = ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=attribute_name, ctx=ast.Store())
        try:
            value_node = ast.Constant(value=ast.literal_eval(default_value))
        except (ValueError, SyntaxError):
            value_node = ast.Name(id=default_value, ctx=ast.Load())
        assignment = ast.Assign(targets=[target], value=value_node)

        if len(init_method.body) == 1 and (isinstance(init_method.body[0], ast.Pass) or (isinstance(init_method.body[0], ast.Expr) and isinstance(init_method.body[0].value, ast.Constant) and init_method.body[0].value.value is Ellipsis)):
            init_method.body = []

        init_method.body.append(assignment)
        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully added attribute '{attribute_name}' to __init__ in class '{class_name}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while adding attribute: {e}"


async def add_decorator_to_function(path: str, function_name: str, decorator_code: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Adds a decorator to a specific function or method in a Python file.
    """
    logger.info(f"Adding decorator '{decorator_code}' to function '{function_name}' in file '{path}'")
    if not decorator_code.strip().startswith('@'):
        return "Error: `decorator_code` must be a valid decorator string starting with '@'."
    try:
        parsed_dummy = ast.parse(f"{decorator_code}\ndef d(): pass")
        decorator_node = parsed_dummy.body[0].decorator_list[0]
    except (SyntaxError, IndexError) as e:
        return f"Error: Invalid decorator syntax provided. Details: {e}"

    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        target_function = next((node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name), None)

        if not target_function:
            return f"Error: Function or method '{function_name}' not found in '{path}'."

        target_function.decorator_list.insert(0, decorator_node)
        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully added decorator '{decorator_code}' to function '{function_name}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while adding decorator: {e}"


class RenameTransformer(ast.NodeTransformer):
    def __init__(self, old_name, new_name):
        self.old_name = old_name
        self.new_name = new_name
    def visit_Name(self, node):
        if node.id == self.old_name: node.id = self.new_name
        return node
    def visit_FunctionDef(self, node):
        if node.name == self.old_name: node.name = self.new_name
        self.generic_visit(node)
        return node
    def visit_AsyncFunctionDef(self, node):
        if node.name == self.old_name: node.name = self.new_name
        self.generic_visit(node)
        return node
    def visit_ClassDef(self, node):
        if node.name == self.old_name: node.name = self.new_name
        self.generic_visit(node)
        return node
    def visit_arg(self, node):
        if node.arg == self.old_name: node.arg = self.new_name
        return node


async def rename_symbol_in_file(path: str, old_name: str, new_name: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Safely renames a symbol within a single Python file using an AST transformer.
    """
    logger.info(f"Attempting to rename '{old_name}' to '{new_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        new_tree = RenameTransformer(old_name, new_name).visit(tree)
        ast.fix_missing_locations(new_tree)
        new_code = ast.unparse(new_tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully renamed '{old_name}' to '{new_name}' in '{path}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred during symbol renaming: {e}"


async def append_to_function(path: str, function_name: str, code_to_append: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Appends code to the body of a specific function in a Python file.
    """
    logger.info(f"Appending code to function '{function_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        append_nodes = ast.parse(code_to_append).body
        target_function = next((node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name), None)

        if not target_function:
            return f"Error: Function '{function_name}' not found in '{path}'."

        insert_index = len(target_function.body)
        for i, body_node in enumerate(target_function.body):
            if isinstance(body_node, ast.Return):
                insert_index = i
                break

        if len(target_function.body) == 1 and (isinstance(target_function.body[0], ast.Pass) or (isinstance(target_function.body[0], ast.Expr) and target_function.body[0].value.value is Ellipsis)):
            target_function.body = []
            insert_index = 0

        for i, new_node in enumerate(append_nodes):
            target_function.body.insert(insert_index + i, new_node)

        new_code = ast.unparse(tree)
        path_obj.write_text(new_code, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_code)
        await code_intelligence_service.update_index_for_file(path_obj, new_code)

        return f"Successfully appended code to function '{function_name}' in '{path}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or `code_to_append`. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while appending to function: {e}"


async def replace_node_in_file(path: str, node_name: str, new_code: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Replaces a top-level function or class node in a file with new code.
    """
    logger.info(f"Attempting to replace node '{node_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        new_code_tree = ast.parse(new_code)

        if not new_code_tree.body or not isinstance(new_code_tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return f"Error: `new_code` does not contain a valid function/class definition."

        new_node = new_code_tree.body[0]
        if new_node.name != node_name:
            return f"Error: Node name in `new_code` ('{new_node.name}') does not match `node_name` ('{node_name}')."

        node_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and existing_node.name == node_name:
                tree.body[i] = new_node
                node_replaced = True
                break

        if not node_replaced:
            return f"Error: Node '{node_name}' not found in '{path}'."

        new_content = ast.unparse(tree)
        path_obj.write_text(new_content, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_content)
        await code_intelligence_service.update_index_for_file(path_obj, new_content)

        return f"Successfully replaced node '{node_name}' in '{path}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or `new_code`. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while replacing node: {e}"


async def replace_method_in_class(path: str, class_name: str, method_name: str, new_code: str, vector_context_service: VectorContextService, code_intelligence_service: CodeIntelligenceService) -> str:
    """
    Replaces a specific method within a class in a file with new code.
    """
    logger.info(f"Replacing method '{method_name}' in class '{class_name}' in file '{path}'")
    path_obj = Path(path)
    if not path_obj.exists():
        return f"Error: File not found at '{path}'."
    try:
        content = path_obj.read_text(encoding='utf-8')
        tree = ast.parse(content)
        new_code_tree = ast.parse(new_code)

        if not new_code_tree.body or not isinstance(new_code_tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            return f"Error: `new_code` does not contain a valid method definition."

        new_method_node = new_code_tree.body[0]
        if new_method_node.name != method_name:
            return f"Error: Name in `new_code` ('{new_method_node.name}') doesn't match `method_name` ('{method_name}')."

        class_node = next((node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name), None)
        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        method_replaced = False
        for i, class_body_node in enumerate(class_node.body):
            if isinstance(class_body_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and class_body_node.name == method_name:
                class_node.body[i] = new_method_node
                method_replaced = True
                break

        if not method_replaced:
            return f"Error: Method '{method_name}' not found in class '{class_name}'."

        new_content = ast.unparse(tree)
        path_obj.write_text(new_content, encoding='utf-8')
        await vector_context_service.reindex_file(path_obj, new_content)
        await code_intelligence_service.update_index_for_file(path_obj, new_content)

        return f"Successfully replaced method '{method_name}' in class '{class_name}'."
    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or `new_code`. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while replacing method: {e}"