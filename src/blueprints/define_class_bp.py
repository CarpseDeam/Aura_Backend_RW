# blueprints/define_class_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The name of the class to create.",
        },
        "bases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of base classes to inherit from, e.g., ['Exception', 'MyMixin']. Can be empty."
        }
    },
    "required": ["name"],
}

blueprint = Blueprint(
    id="define_class",
    description="Creates an empty Python class definition with optional base classes. The body will be empty (pass).",
    parameters=params,
    action_function_name="define_class"
)