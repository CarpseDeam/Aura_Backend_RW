# blueprints/add_function_to_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to add the function to.",
        },
        "function_code": {
            "type": "string",
            "description": "A string containing the complete, well-formatted Python code for the new function, including its signature and body.",
        }
    },
    "required": ["path", "function_code"],
}

blueprint = Blueprint(
    id="add_function_to_file",
    description="Adds a new function to an existing Python file without overwriting the file's other contents. This is the preferred way to add new functions or helper methods to a file.",
    parameters=params,
    action_function_name="add_function_to_file"
)