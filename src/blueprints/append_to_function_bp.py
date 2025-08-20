# blueprints/append_to_function_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file containing the function.",
        },
        "function_name": {
            "type": "string",
            "description": "The name of the function to append code to.",
        },
        "code_to_append": {
            "type": "string",
            "description": "A string of one or more lines of Python code to be appended to the end of the function's body, before any existing return statement.",
        }
    },
    "required": ["path", "function_name", "code_to_append"],
}

blueprint = Blueprint(
    id="append_to_function",
    description="Appends Python code to the body of an existing function in a file. This is useful for iteratively building up a function's logic or adding statements like logging.",
    parameters=params,
    action_function_name="append_to_function"
)