# blueprints/get_mission_log_bp.py
from src.foundry.blueprints import Blueprint

params = { "type": "object", "properties": {}, "required": [] }

blueprint = Blueprint(
    id="get_mission_log",
    description="Retrieves the current list of all tasks (both pending and completed) from the Agent TODO list.",
    parameters=params,
    action_function_name="get_mission_log"
)