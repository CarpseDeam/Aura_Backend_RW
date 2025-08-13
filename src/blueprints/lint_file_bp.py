# blueprints/lint_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to lint for style errors.",
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="lint_file",
    description="Checks a Python file for style issues (like PEP8) and reports the findings. Useful for ensuring code quality.",
    parameters=params,
    action_function_name="lint_file"
)