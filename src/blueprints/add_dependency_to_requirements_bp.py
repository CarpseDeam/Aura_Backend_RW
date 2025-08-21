# blueprints/add_dependency_to_requirements_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "dependencies": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "A list of Python packages to add, e.g., ['fastapi', 'uvicorn[standard]']",
        },
        "path": {
            "type": "string",
            "description": "The path to the requirements.txt file. Defaults to 'requirements.txt' in the project root.",
        }
    },
    "required": ["dependencies"],
}

blueprint = Blueprint(
    id="add_dependency_to_requirements",
    description="The one and only tool for managing dependencies. Use this to add packages to 'requirements.txt'. This tool automatically creates the file if it doesn't exist, so DO NOT use 'write_file' or 'create_file' to create 'requirements.txt' separately.",
    parameters=params,
    action_function_name="add_dependency_to_requirements"
)