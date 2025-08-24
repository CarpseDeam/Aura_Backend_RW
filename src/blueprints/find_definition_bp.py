# blueprints/find_definition_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "symbol_name": {
            "type": "string",
            "description": "The exact name of the function or class to find.",
        }
    },
    "required": ["symbol_name"],
}

blueprint = Blueprint(
    id="find_definition",
    description="Precisely locates the definition of a function or class within the project using the code index. Answers 'Where is X defined?'.",
    parameters=params,
    action_function_name="find_definition"
)