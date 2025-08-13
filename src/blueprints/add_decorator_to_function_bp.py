# blueprints/add_decorator_to_function_bp.py
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
            "description": "The name of the function or method to add the decorator to.",
        },
        "decorator_code": {
            "type": "string",
            "description": "The decorator to add, as a string (e.g., '@staticmethod', '@app.route(\"/hello\")'). Include the '@' symbol.",
        }
    },
    "required": ["path", "function_name", "decorator_code"],
}

blueprint = Blueprint(
    id="add_decorator_to_function",
    description="Adds a decorator to an existing function or method in a Python file. This is essential for web frameworks and class methods.",
    parameters=params,
    action_function_name="add_decorator_to_function"
)