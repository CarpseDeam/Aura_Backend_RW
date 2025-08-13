# blueprints/add_parameter_to_function_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file containing the function.",
        },
        "function_name": {
            "type": "string",
            "description": "The name of the function or method to modify.",
        },
        "parameter_name": {
            "type": "string",
            "description": "The name of the new parameter to add (e.g., 'new_id', 'user_data').",
        },
        "parameter_type": {
            "type": "string",
            "description": "Optional. The type hint for the new parameter (e.g., 'str', 'int', 'Optional[str]').",
        },
        "default_value": {
            "type": "string",
            "description": "Optional. A string representing the default value (e.g., 'None', \"'default'\", '[]'). If not provided, the parameter will be positional-only.",
        }
    },
    "required": ["path", "function_name", "parameter_name"],
}

blueprint = Blueprint(
    id="add_parameter_to_function",
    description="Surgically adds a new parameter to a function or method's signature. Can specify a type hint and a default value.",
    parameters=params,
    action_function_name="add_parameter_to_function"
)