# blueprints/add_class_to_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to add the class to.",
        },
        "class_code": {
            "type": "string",
            "description": "A string containing the complete, well-formatted Python code for the new class, including its definition, methods, and docstrings.",
        }
    },
    "required": ["path", "class_code"],
}

blueprint = Blueprint(
    id="add_class_to_file",
    description="Adds a new class definition to an existing Python file without overwriting other contents. This is the preferred way to create new classes.",
    parameters=params,
    action_function_name="add_class_to_file"
)