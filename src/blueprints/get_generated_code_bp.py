# blueprints/get_generated_code_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {},
    "required": []
}

blueprint = Blueprint(
    id="get_generated_code",
    description="Returns the Python code generated so far in the session from all previous code-building actions.",
    parameters=params,
    action_function_name="get_generated_code"
)