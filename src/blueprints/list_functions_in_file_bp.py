# blueprints/list_functions_in_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to inspect.",
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="list_functions_in_file",
    description="Inspects a Python file and lists the names of all top-level functions defined within it. Useful for understanding a file's structure before modifying it.",
    parameters=params,
    action_function_name="list_functions_in_file"
)