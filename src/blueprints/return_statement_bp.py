# blueprints/return_statement_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "description": "The literal or variable name to return (e.g., \"'Success'\", \"x\")."}
    },
    "required": ["value"]
}

blueprint = Blueprint(
    id="return_statement",
    description="Creates a Python `return` statement inside a function.",
    parameters=params,
    action_function_name="return_statement"
)