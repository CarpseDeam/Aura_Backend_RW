# blueprints/add_attribute_to_init_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file containing the class.",
        },
        "class_name": {
            "type": "string",
            "description": "The name of the class to add the attribute to.",
        },
        "attribute_name": {
            "type": "string",
            "description": "The name of the attribute to create (e.g., 'name', 'user_id').",
        },
        "default_value": {
            "type": "string",
            "description": "The value to assign to the attribute. This can be a literal (e.g., \"'default'\", \"None\", \"[]\") or a variable name passed to __init__.",
        }
    },
    "required": ["path", "class_name", "attribute_name", "default_value"],
}

blueprint = Blueprint(
    id="add_attribute_to_init",
    description="Adds a new attribute (e.g., 'self.name = name') to the __init__ method of a class. If __init__ doesn't exist, it will be created.",
    parameters=params,
    action_function_name="add_attribute_to_init"
)