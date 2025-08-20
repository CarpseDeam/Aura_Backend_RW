# blueprints/add_method_to_class_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file containing the class.",
        },
        "class_name": {
            "type": "string",
            "description": "The name of the class to add the method to.",
        },
        "name": {
            "type": "string",
            "description": "The name of the method to create (e.g., '__init__', 'my_method').",
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of argument names for the method. For instance methods, the first argument should always be 'self'."
        },
        "is_async": {
            "type": "boolean",
            "description": "Set to true to create an 'async def' method. Defaults to false."
        }
    },
    "required": ["path", "class_name", "name", "args"],
}

blueprint = Blueprint(
    id="add_method_to_class",
    description="Adds a new, empty method (with `pass`) to an existing class in a Python file. This modifies the file in place.",
    parameters=params,
    action_function_name="add_method_to_class"
)