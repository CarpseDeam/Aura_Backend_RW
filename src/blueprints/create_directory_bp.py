# blueprints/create_directory_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The full path of the directory to create.",
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="create_directory",
    description="Creates a new, empty directory at the specified path.",
    parameters=params,
    action_function_name="create_directory"
)