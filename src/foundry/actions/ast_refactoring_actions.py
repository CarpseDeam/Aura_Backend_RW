# foundry/actions/ast_refactoring_actions.py
"""
Contains actions that modify or refactor existing code constructs using AST.
These tools are for targeted changes like renaming symbols or appending
logic to functions.
"""
import ast
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def add_parameter_to_function(path: str, function_name: str, parameter_name: str, parameter_type: Optional[str] = None,
                              default_value: Optional[str] = None) -> str:
    """
    Adds a new parameter to a function's signature using AST.

    This function can handle adding parameters with or without default values,
    and correctly places them in the function's signature.
    """
    logger.info(f"Adding parameter '{parameter_name}' to function '{function_name}' in file '{path}'")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)
        func_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                func_node = node
                break

        if not func_node:
            return f"Error: Function '{function_name}' not found in '{path}'."

        # Create the new argument
        new_arg = ast.arg(arg=parameter_name, annotation=None)
        if parameter_type:
            new_arg.annotation = ast.Name(id=parameter_type, ctx=ast.Load())

        # Check for existing parameter with the same name
        for arg in func_node.args.args:
            if arg.arg == parameter_name:
                return f"Error: Parameter '{parameter_name}' already exists in function '{function_name}'."
        for arg in func_node.args.kwonlyargs:
            if arg.arg == parameter_name:
                return f"Error: Parameter '{parameter_name}' already exists in function '{function_name}'."

        if default_value is not None:
            # Argument with a default value
            try:
                value_node = ast.Constant(value=ast.literal_eval(default_value))
            except (ValueError, SyntaxError):
                value_node = ast.Name(id=default_value, ctx=ast.Load())

            # Keyword-only arguments are generally safer for new additions with defaults
            func_node.args.kwonlyargs.append(new_arg)
            func_node.args.kw_defaults.append(value_node)
        else:
            # Positional argument without a default value
            # Must be inserted before any args that have defaults.
            num_args = len(func_node.args.args)
            num_defaults = len(func_node.args.defaults)
            first_default_idx = num_args - num_defaults

            func_node.args.args.insert(first_default_idx, new_arg)

        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        return f"Successfully added parameter '{parameter_name}' to function '{function_name}' in '{path}'."

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding parameter: {e}"
        logger.exception(error_message)
        return error_message


def add_attribute_to_init(path: str, class_name: str, attribute_name: str, default_value: str) -> str:
    """
    Adds a 'self.attribute = value' line to the __init__ of a class.
    If __init__ does not exist, it will be created.
    """
    logger.info(f"Adding attribute '{attribute_name}' to class '{class_name}' in file '{path}'")

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
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break

        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        init_method = None
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                init_method = node
                break

        # If __init__ doesn't exist, create it.
        if not init_method:
            logger.info(f"__init__ not found in '{class_name}'. Creating a new one.")
            # Create 'self' argument
            self_arg = ast.arg(arg='self', annotation=None)
            # Create arguments object
            args = ast.arguments(args=[self_arg], posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[])
            # Create an empty body
            body = []
            # Create the FunctionDef for __init__
            init_method = ast.FunctionDef(name='__init__', args=args, body=body, decorator_list=[], returns=None)
            # Add the new __init__ method to the top of the class body
            class_node.body.insert(0, init_method)

        # Create the assignment 'self.attribute = value'
        target = ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=attribute_name, ctx=ast.Store())
        try:
            # Try to evaluate the default_value as a Python literal
            value_node = ast.Constant(value=ast.literal_eval(default_value))
        except (ValueError, SyntaxError):
            # If it fails, treat it as a variable name
            value_node = ast.Name(id=default_value, ctx=ast.Load())

        assignment = ast.Assign(targets=[target], value=value_node)

        # If the init body is just 'pass' or '...', remove it.
        if (len(init_method.body) == 1 and
                (isinstance(init_method.body[0], ast.Pass) or
                 (isinstance(init_method.body[0], ast.Expr) and isinstance(init_method.body[0].value, ast.Constant) and
                  init_method.body[0].value.value is Ellipsis))):
            init_method.body = []

        init_method.body.append(assignment)

        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully added attribute '{attribute_name}' to __init__ in class '{class_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding attribute: {e}"
        logger.exception(error_message)
        return error_message


def add_decorator_to_function(path: str, function_name: str, decorator_code: str) -> str:
    """
    Adds a decorator to a specific function or method in a Python file using AST.
    """
    logger.info(f"Attempting to add decorator '{decorator_code}' to function '{function_name}' in file '{path}'")

    if not decorator_code.strip().startswith('@'):
        return "Error: `decorator_code` must be a valid decorator string starting with '@'."

    try:
        # A trick to parse a decorator string: wrap it in a dummy function def
        dummy_function_with_decorator = f"{decorator_code}\ndef dummy(): pass"
        parsed_dummy = ast.parse(dummy_function_with_decorator)
        decorator_node = parsed_dummy.body[0].decorator_list[0]
    except (SyntaxError, IndexError) as e:
        return f"Error: Invalid decorator syntax provided in `decorator_code`. Details: {e}"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)

        target_function = None
        # We use ast.walk to find the function, even if it's nested inside a class.
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                target_function = node
                break

        if not target_function:
            return f"Error: Function or method '{function_name}' not found in '{path}'."

        # Insert the new decorator at the beginning of the list.
        target_function.decorator_list.insert(0, decorator_node)

        ast.fix_missing_locations(tree)
        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully added decorator '{decorator_code}' to function '{function_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while adding decorator: {e}"
        logger.exception(error_message)
        return error_message


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

    def visit_ClassDef(self, node):
        if node.name == self.old_name:
            node.name = self.new_name
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        if node.arg == self.old_name:
            node.arg = self.new_name
        return node


def rename_symbol_in_file(path: str, old_name: str, new_name: str) -> str:
    """
    Safely renames a symbol within a single Python file using an AST transformer.
    """
    logger.info(f"Attempting to rename '{old_name}' to '{new_name}' in file '{path}'")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)

        transformer = RenameTransformer(old_name, new_name)
        new_tree = transformer.visit(tree)

        ast.fix_missing_locations(new_tree)

        new_code = ast.unparse(new_tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully renamed '{old_name}' to '{new_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}'. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred during symbol renaming: {e}"
        logger.exception(error_message)
        return error_message


def append_to_function(path: str, function_name: str, code_to_append: str) -> str:
    """
    Appends code to the body of a specific function in a Python file using AST.
    """
    logger.info(f"Attempting to append code to function '{function_name}' in file '{path}'")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        tree = ast.parse(content)

        # Parse the code snippet to be appended
        append_nodes = ast.parse(code_to_append).body

        target_function = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                target_function = node
                break

        if not target_function:
            return f"Error: Function '{function_name}' not found in '{path}'."

        # Find where to insert the new code. We want to insert it before the return statement if one exists.
        insert_index = len(target_function.body)
        for i, body_node in enumerate(target_function.body):
            if isinstance(body_node, ast.Return):
                insert_index = i
                break

        # If the function body is just 'pass', remove it before appending.
        if len(target_function.body) == 1 and isinstance(target_function.body[0], ast.Expr) and isinstance(
                target_function.body[0].value, ast.Constant) and target_function.body[0].value.value is Ellipsis:
            target_function.body = []
            insert_index = 0
        elif len(target_function.body) == 1 and isinstance(target_function.body[0], ast.Pass):
            target_function.body = []
            insert_index = 0

        # Insert the new nodes at the calculated position
        for i, new_node in enumerate(append_nodes):
            target_function.body.insert(insert_index + i, new_node)

        new_code = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        success_message = f"Successfully appended code to function '{function_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or in `code_to_append`. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while appending to function: {e}"
        logger.exception(error_message)
        return error_message


def replace_node_in_file(path: str, node_name: str, new_code: str) -> str:
    """
    Replaces a top-level function or class node in a file with new code.
    """
    logger.info(f"Attempting to replace node '{node_name}' in file '{path}'")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        # Parse the original file content and the new code snippet
        tree = ast.parse(content)
        new_code_tree = ast.parse(new_code)

        # Ensure the new code contains one valid top-level node
        if not new_code_tree.body or not isinstance(new_code_tree.body[0], (ast.FunctionDef, ast.ClassDef)):
            return f"Error: The provided `new_code` does not contain a single, valid top-level function or class definition."

        new_node = new_code_tree.body[0]

        # Check if the new node's name matches the target node_name
        if new_node.name != node_name:
            return f"Error: The name of the node in `new_code` ('{new_node.name}') does not match the `node_name` to be replaced ('{node_name}')."

        # Find the node to replace in the original tree
        node_replaced = False
        for i, existing_node in enumerate(tree.body):
            if isinstance(existing_node, (ast.FunctionDef, ast.ClassDef)) and existing_node.name == node_name:
                tree.body[i] = new_node
                node_replaced = True
                break

        if not node_replaced:
            return f"Error: Node '{node_name}' not found as a top-level function or class in '{path}'."

        # Unparse the modified tree and write it back to the file
        new_content = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        success_message = f"Successfully replaced node '{node_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or in the provided `new_code`. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while replacing node: {e}"
        logger.exception(error_message)
        return error_message

def replace_method_in_class(path: str, class_name: str, method_name: str, new_code: str) -> str:
    """
    Replaces a specific method within a class in a file with new code.
    """
    logger.info(f"Attempting to replace method '{method_name}' in class '{class_name}' in file '{path}'")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"Error reading file at '{path}': {e}"

    try:
        # Parse the original file content and the new code snippet
        tree = ast.parse(content)
        new_code_tree = ast.parse(new_code)

        if not new_code_tree.body or not isinstance(new_code_tree.body[0], ast.FunctionDef):
            return f"Error: The provided `new_code` does not contain a single, valid method definition."

        new_method_node = new_code_tree.body[0]

        if new_method_node.name != method_name:
            return f"Error: The name in `new_code` ('{new_method_node.name}') does not match `method_name` ('{method_name}')."

        # Find the target class node
        class_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break

        if not class_node:
            return f"Error: Class '{class_name}' not found in '{path}'."

        # Find and replace the method within the class body
        method_replaced = False
        for i, class_body_node in enumerate(class_node.body):
            if isinstance(class_body_node, ast.FunctionDef) and class_body_node.name == method_name:
                class_node.body[i] = new_method_node
                method_replaced = True
                break

        if not method_replaced:
            return f"Error: Method '{method_name}' not found in class '{class_name}' in '{path}'."

        # Unparse the modified tree and write it back
        new_content = ast.unparse(tree)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        success_message = f"Successfully replaced method '{method_name}' in class '{class_name}' in '{path}'."
        logger.info(success_message)
        return success_message

    except SyntaxError as e:
        return f"Error: Syntax error in file '{path}' or in `new_code`. Details: {e}"
    except Exception as e:
        error_message = f"An unexpected error occurred while replacing method: {e}"
        logger.exception(error_message)
        return error_message