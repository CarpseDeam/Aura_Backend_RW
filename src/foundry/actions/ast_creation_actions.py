# foundry/actions/ast_creation_actions.py
"""
Contains actions that create and return new, disconnected AST nodes.
These are used for building new code in memory before it's written to a file.
"""
import ast
import logging
from typing import List, Any

logger = logging.getLogger(__name__)

def assign_variable(variable_name: str, value: str) -> ast.Assign:
    """Creates an AST node for a variable assignment."""
    logger.info(f"Creating AST for: {variable_name} = {value}")
    target = ast.Name(id=variable_name, ctx=ast.Store())
    try:
        evaluated_value = ast.literal_eval(value)
        value_node = ast.Constant(value=evaluated_value)
    except (ValueError, SyntaxError):
        value_node = ast.Name(id=value, ctx=ast.Load())
    assignment = ast.Assign(targets=[target], value=value_node)
    ast.fix_missing_locations(assignment)
    return assignment

def define_function(name: str, args: List[str] = []) -> ast.FunctionDef:
    """Creates an AST node for a function definition."""
    logger.info(f"Creating AST for function: def {name}({', '.join(args)}): pass")
    arguments = ast.arguments(
        args=[ast.arg(arg=name) for name in args],
        posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[]
    )
    body = [ast.Pass()]
    func_def = ast.FunctionDef(
        name=name, args=arguments, body=body, decorator_list=[]
    )
    ast.fix_missing_locations(func_def)
    return func_def

def function_call(func_name: str, args: List[Any] = []) -> ast.Expr:
    """Creates an AST node for a function call."""
    logger.info(f"Creating AST for function call: {func_name}({', '.join(map(str, args))})")
    arg_nodes = []
    for arg in args:
        try:
            val = ast.literal_eval(arg)
            arg_nodes.append(ast.Constant(value=val))
        except (ValueError, SyntaxError):
            arg_nodes.append(ast.Name(id=str(arg), ctx=ast.Load()))
    call_node = ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load()),
        args=arg_nodes,
        keywords=[]
    )
    expr = ast.Expr(value=call_node)
    ast.fix_missing_locations(expr)
    return expr

def return_statement(value: str) -> ast.Return:
    """Creates an AST node for a return statement."""
    logger.info(f"Creating AST for: return {value}")
    try:
        val = ast.literal_eval(value)
        value_node = ast.Constant(value=val)
    except (ValueError, SyntaxError):
        value_node = ast.Name(id=value, ctx=ast.Load())
    return_node = ast.Return(value=value_node)
    ast.fix_missing_locations(return_node)
    return return_node

def define_class(name: str, bases: List[str] = []) -> ast.ClassDef:
    """
    Creates an AST node for a class definition.

    Args:
        name: The name of the class.
        bases: A list of strings representing the names of base classes.

    Returns:
        An ast.ClassDef node representing the new class.
    """
    logger.info(f"Creating AST for class: class {name}({', '.join(bases) if bases else ''}): pass")

    # Convert base class names (strings) into AST nodes
    base_nodes = [ast.Name(id=base, ctx=ast.Load()) for base in bases]

    # Create an empty body with a 'pass' statement
    body = [ast.Pass()]

    # Create the ClassDef node
    class_def = ast.ClassDef(
        name=name,
        bases=base_nodes,
        keywords=[],
        body=body,
        decorator_list=[]
    )

    ast.fix_missing_locations(class_def)
    return class_def