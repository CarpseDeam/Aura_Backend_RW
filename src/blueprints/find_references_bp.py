# blueprints/find_references_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "symbol_name": {
            "type": "string",
            "description": "The exact name of the function or class to find references for.",
        }
    },
    "required": ["symbol_name"],
}

blueprint = Blueprint(
    id="find_references",
    description="Finds all locations in the code that call or reference a specific function or class. Answers 'Where is X used?'.",
    parameters=params,
    action_function_name="find_references"
)
