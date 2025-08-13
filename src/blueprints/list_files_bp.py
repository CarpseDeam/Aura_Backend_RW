# blueprints/list_files_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The directory path to list. Defaults to the current directory if not provided.",
        }
    },
    "required": [],
}

blueprint = Blueprint(
    id="list_files",
    description="Lists all files and directories in a specified path.",
    parameters=params,
    action_function_name="list_files"
)