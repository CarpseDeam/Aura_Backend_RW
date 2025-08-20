# blueprints/create_project_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "project_name": {
            "type": "string",
            "description": "The name of the new project to create. Use a short, filesystem-friendly name (e.g., 'my-web-app').",
        }
    },
    "required": ["project_name"],
}

blueprint = Blueprint(
    id="create_project",
    description="Creates a new project directory in the 'projects' workspace and sets it as the active project for all subsequent file operations.",
    parameters=params,
    action_function_name="create_project"
)