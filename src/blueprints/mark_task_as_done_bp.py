# blueprints/mark_task_as_done_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "integer",
            "description": "The unique ID number of the task to be marked as completed.",
        }
    },
    "required": ["task_id"],
}

blueprint = Blueprint(
    id="mark_task_as_done",
    description="Marks a task in the Agent TODO list as done. Use 'get_mission_log' first to find the correct task ID.",
    parameters=params,
    action_function_name="mark_task_as_done"
)