# blueprints/replace_node_in_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to modify.",
        },
        "node_name": {
            "type": "string",
            "description": "The name of the top-level function or class to be replaced.",
        },
        "new_code": {
            "type": "string",
            "description": "The complete, new source code for the function or class. This will fully replace the old one.",
        }
    },
    "required": ["path", "node_name", "new_code"],
}

blueprint = Blueprint(
    id="replace_node_in_file",
    description="Replaces an entire top-level function or class in a Python file with new code. This is the preferred tool for refactoring or changing the logic of existing code blocks.",
    parameters=params,
    action_function_name="replace_node_in_file"
)