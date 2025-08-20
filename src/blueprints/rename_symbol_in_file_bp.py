# blueprints/rename_symbol_in_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to modify.",
        },
        "old_name": {
            "type": "string",
            "description": "The current name of the variable, function, or class to be renamed.",
        },
        "new_name": {
            "type": "string",
            "description": "The new name for the symbol.",
        }
    },
    "required": ["path", "old_name", "new_name"],
}

blueprint = Blueprint(
    id="rename_symbol_in_file",
    description="Safely renames a symbol (variable, function, class) and all its usages throughout a single Python file. This is the preferred tool for refactoring names.",
    parameters=params,
    action_function_name="rename_symbol_in_file"
)