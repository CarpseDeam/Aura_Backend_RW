# blueprints/define_function_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The name of the function."},
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of argument names for the function."
        }
    },
    "required": ["name"]
}

blueprint = Blueprint(
    id="define_function",
    description="Defines a new Python function with specified arguments. The body will be empty (pass).",
    parameters=params,
    action_function_name="define_function"
)