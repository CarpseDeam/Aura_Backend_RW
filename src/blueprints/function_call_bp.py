# blueprints/function_call_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "func_name": {
            "type": "string",
            "description": "The name of the function to call.",
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of arguments for the function call (e.g., [\"'a string'\", \"42\", \"some_variable\"]).",
        },
    },
    "required": ["func_name"],
}

blueprint = Blueprint(
    id="function_call",
    description=(
        "Creates a Python function call statement. This is useful for invoking "
        "existing functions within the code. Arguments are provided as a list of strings. "
        "Each argument is parsed as a literal (e.g., \"'hello'\", \"123\") or "
        "treated as a variable name if literal parsing fails."
    ),
    parameters=params,
    action_function_name="function_call"
)