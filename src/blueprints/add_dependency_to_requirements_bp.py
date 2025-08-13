# blueprints/add_dependency_to_requirements_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "dependency": {
            "type": "string",
            "description": "The name of the Python package to add, e.g., 'flask' or 'pytest==7.4.0'.",
        },
        "path": {
            "type": "string",
            "description": "The path to the requirements.txt file. Defaults to 'requirements.txt' in the project root.",
        }
    },
    "required": ["dependency"],
}

blueprint = Blueprint(
    id="add_dependency_to_requirements",
    description="Safely adds a dependency to a requirements.txt file. It creates the file if it doesn't exist and appends the dependency if it's not already present. This is the REQUIRED tool for managing dependencies.",
    parameters=params,
    action_function_name="add_dependency_to_requirements"
)