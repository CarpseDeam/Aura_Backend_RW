# blueprints/assign_variable_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "variable_name": {
            "type": "string",
            "description": "The name of the variable to create or assign to.",
        },
        "value": {
            "type": "string",
            "description": "The value to assign. This can be a literal (e.g., \"123\", \"'hello'\", \"True\") or an identifier for another variable (e.g., \"other_var\").",
        },
    },
    "required": ["variable_name", "value"],
}

blueprint = Blueprint(
    id="assign_variable",
    description="Creates a Python variable assignment AST node.",
    parameters=params,
    action_function_name="assign_variable"
)