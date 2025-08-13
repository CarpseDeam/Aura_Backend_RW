# blueprints/request_user_input_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question to ask the user.",
        }
    },
    "required": ["question"],
}

blueprint = Blueprint(
    id="request_user_input",
    description="Asks the user a clarifying question and waits for their response. Use this when you are uncertain about how to proceed or need confirmation for a destructive action.",
    parameters=params,
    action_function_name="request_user_input"
)