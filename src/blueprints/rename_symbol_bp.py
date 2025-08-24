# src/blueprints/rename_symbol_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "old_name": {
            "type": "string",
            "description": "The current name of the function or class to be renamed.",
        },
        "new_name": {
            "type": "string",
            "description": "The new name for the symbol.",
        }
    },
    "required": ["old_name", "new_name"],
}

blueprint = Blueprint(
    id="rename_symbol",
    description="Performs a project-wide safe rename of a function or class and all of its usages using the code index. This is the most powerful refactoring tool for renaming.",
    parameters=params,
    action_function_name="rename_symbol"
)