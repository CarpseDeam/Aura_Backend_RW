# blueprints/get_code_for_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to inspect.",
        },
        "function_name": {
            "type": "string",
            "description": "The name of the function to get the source code for.",
        }
    },
    "required": ["path", "function_name"],
}

blueprint = Blueprint(
    id="get_code_for",
    description="Extracts and returns the full source code of a specific top-level function from a Python file.",
    parameters=params,
    action_function_name="get_code_for"
)