# blueprints/pip_install_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "requirements_path": {
            "type": "string",
            "description": "Optional. The path to the requirements.txt file. Defaults to 'requirements.txt' in the project root.",
        }
    },
    "required": [],
}

blueprint = Blueprint(
    id="pip_install",
    description="Installs Python packages from a requirements.txt file. If a 'venv' directory does not exist in the project root, it will be created automatically.",
    parameters=params,
    action_function_name="pip_install"
)