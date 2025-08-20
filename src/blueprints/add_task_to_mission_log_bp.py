# blueprints/add_task_to_mission_log_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "A clear, concise, user-facing description of the task to be added to the Agent TODO list.",
        },
        "tool_call": {
            "type": "object",
            "description": "Optional. The machine-readable tool call dictionary associated with this task.",
        }
    },
    "required": ["description"],
}

blueprint = Blueprint(
    id="add_task_to_mission_log",
    description="Adds a new task to the project's shared to-do list (the Agent TODO). Can include the underlying tool call for autonomous execution.",
    parameters=params,
    action_function_name="add_task_to_mission_log"
)