# src/blueprints/get_dependencies_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "symbol_name": {
            "type": "string",
            "description": "The exact name of the function or class to find its dependencies.",
        }
    },
    "required": ["symbol_name"],
}

blueprint = Blueprint(
    id="get_dependencies",
    description="Lists all other functions and methods that a given function/class calls. Answers 'What does X use?'.",
    parameters=params,
    action_function_name="get_dependencies"
)