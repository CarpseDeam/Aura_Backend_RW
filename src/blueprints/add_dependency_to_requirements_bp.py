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
    description="The REQUIRED and ONLY tool for managing dependencies. It safely adds one or more packages to a requirements.txt file. It creates the file if it doesn't exist and appends the dependencies if they are not already present.",
    parameters=params,
    action_function_name="add_dependency_to_requirements"
)