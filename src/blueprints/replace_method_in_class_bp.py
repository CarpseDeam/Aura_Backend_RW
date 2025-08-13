# blueprints/replace_method_in_class_bp.py
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
            "description": "The name of the class containing the method to be replaced.",
        },
        "method_name": {
            "type": "string",
            "description": "The name of the method to be replaced (e.g., '__init__', 'my_method').",
        },
        "new_code": {
            "type": "string",
            "description": "The complete, new source code for the method. This will fully replace the old one.",
        }
    },
    "required": ["path", "class_name", "method_name", "new_code"],
}

blueprint = Blueprint(
    id="replace_method_in_class",
    description="Surgically replaces an entire method within a specific class in a Python file. This is the preferred tool for refactoring or changing the logic of an existing method.",
    parameters=params,
    action_function_name="replace_method_in_class"
)