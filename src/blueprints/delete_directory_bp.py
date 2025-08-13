# blueprints/delete_directory_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The full path of the directory to be recursively deleted.",
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="delete_directory",
    description="Deletes a specified directory and all of its contents. This action is irreversible, so be certain.",
    parameters=params,
    action_function_name="delete_directory"
)