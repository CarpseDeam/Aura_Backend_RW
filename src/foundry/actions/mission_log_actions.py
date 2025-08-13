# foundry/actions/mission_log_actions.py
import logging
from typing import Optional, Dict
from src.services.mission_log_service import MissionLogService

logger = logging.getLogger(__name__)


def add_task_to_mission_log(mission_log_service: MissionLogService, description: str, tool_call: Optional[Dict] = None) -> str:
    """Action to add a new task to the Mission Log, with an optional machine-readable tool call."""
    try:
        new_task = mission_log_service.add_task(description, tool_call)
        return f"Successfully added task {new_task['id']}: '{description}' to the Agent TODO list."
    except Exception as e:
        logger.error(f"Error adding task to mission log: {e}", exc_info=True)
        return f"Error: Could not add task. {e}"


def mark_task_as_done(mission_log_service: MissionLogService, task_id: int) -> str:
    """Action to mark a task as done."""
    success = mission_log_service.mark_task_as_done(task_id)
    if success:
        return f"Successfully marked task {task_id} as done."
    else:
        return f"Error: Could not find task with ID {task_id}."


def get_mission_log(mission_log_service: MissionLogService) -> str:
    """Action to retrieve the current mission log."""
    tasks = mission_log_service.get_tasks()
    if not tasks:
        return "The Agent TODO list is currently empty."

    log_str = "Current Agent TODO:\n"
    for task in tasks:
        status = "[x]" if task['done'] else "[ ]"
        log_str += f"- {status} ID {task['id']}: {task['description']}\n"

    return log_str.strip()