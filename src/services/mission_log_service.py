# src/services/mission_log_service.py
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import asyncio

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.events import ProjectCreated

if TYPE_CHECKING:
    from src.core.managers import ProjectManager

logger = logging.getLogger(__name__)
MISSION_LOG_FILENAME = "mission_log.json"


class MissionLogService:
    """
    Manages the state of the Mission Log (to-do list) for the active project.
    """

    def __init__(self, project_manager: "ProjectManager", event_bus: EventBus):
        self.project_manager = project_manager
        self.event_bus = event_bus
        self.tasks: List[Dict[str, Any]] = []
        self._next_task_id = 1
        self._initial_user_goal = ""
        # We no longer need to subscribe to this event as the service is created fresh per request
        # self.event_bus.subscribe("project_created", self.handle_project_created)
        logger.info("MissionLogService initialized.")

    def _get_log_path(self) -> Optional[Path]:
        """Gets the path to the mission log file for the active project."""
        if self.project_manager.active_project_path:
            return self.project_manager.active_project_path / MISSION_LOG_FILENAME
        return None

    def _save_log_to_disk(self):
        """Saves the current list of tasks to disk."""
        log_path = self._get_log_path()
        if not log_path:
            return

        data_to_save = {
            "initial_goal": self._initial_user_goal,
            "tasks": self.tasks
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2)
            logger.debug(f"Mission Log saved to disk at {log_path}.")
        except IOError as e:
            logger.error(f"Failed to save mission log to {log_path}: {e}")

    async def _notify_ui(self, user_id: str):
        """Notifies the UI of an update via WebSocket."""
        message = {
            "type": "mission_log_updated",
            "content": {"tasks": self.get_tasks()}
        }
        # In a web context, we assume a single client_id for simplicity, but this could be expanded
        await websocket_manager.broadcast_to_user(message, user_id)
        logger.debug(f"UI notified for user {user_id} of mission log update.")

    def load_log_for_active_project(self):
        """Loads the mission log from disk for the currently active project."""
        log_path = self._get_log_path()
        self.tasks = []
        self._next_task_id = 1
        self._initial_user_goal = ""

        if log_path and log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    self.tasks = saved_data.get("tasks", [])
                    self._initial_user_goal = saved_data.get("initial_goal", "")
                if self.tasks:
                    valid_ids = [task.get('id', 0) for task in self.tasks]
                    self._next_task_id = max(valid_ids) + 1 if valid_ids else 1
                logger.info(f"Successfully loaded Mission Log for '{self.project_manager.active_project_name}'")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load or parse mission log at {log_path}: {e}. Starting fresh.")
                self.tasks = []
        else:
            logger.info("No existing mission log found for this project. Starting fresh.")

        # Save on load to ensure file exists for new projects
        self._save_log_to_disk()

    async def set_initial_plan(self, user_id: str, plan_steps: List[str], user_goal: str):
        """Clears all tasks and sets a new plan, storing the original user goal."""
        self.tasks = []
        self._next_task_id = 1
        self._initial_user_goal = user_goal

        for step in plan_steps:
            await self.add_task(user_id=user_id, description=step, notify=False)

        self._save_log_to_disk()
        await self._notify_ui(user_id)
        logger.info(f"Initial plan with {len(self.tasks)} steps has been set for user {user_id}.")

    async def add_task(self, user_id: str, description: str, tool_call: Optional[Dict] = None, notify: bool = True) -> \
    Dict[str, Any]:
        """Adds a new task to the mission log."""
        if not description:
            raise ValueError("Task description cannot be empty.")
        new_task = {
            "id": self._next_task_id,
            "description": description,
            "done": False,
            "tool_call": tool_call,
            "last_error": None
        }
        self.tasks.append(new_task)
        self._next_task_id += 1
        logger.info(f"Added task {new_task['id']}: '{description}'")

        self._save_log_to_disk()
        if notify:
            await self._notify_ui(user_id)
        return new_task

    async def mark_task_as_done(self, user_id: str, task_id: int) -> bool:
        """Marks a specific task as completed."""
        for task in self.tasks:
            if task.get('id') == task_id:
                if not task.get('done'):
                    task['done'] = True
                    task['last_error'] = None  # Clear error on success
                    self._save_log_to_disk()
                    await self._notify_ui(user_id)
                    logger.info(f"Marked task {task_id} as done.")
                return True
        logger.warning(f"Attempted to mark non-existent task {task_id} as done.")
        return False

    def get_tasks(self, done: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Returns a copy of the current tasks, optionally filtered by done status."""
        if done is None:
            return list(self.tasks)
        return [task for task in self.tasks if task.get('done') == done]

    async def clear_all_tasks(self, user_id: str):
        """Removes all tasks from the log."""
        if self.tasks:
            self.tasks = []
            self._next_task_id = 1
            self._initial_user_goal = ""
            self._save_log_to_disk()
            await self._notify_ui(user_id)
            logger.info("All tasks cleared from the Mission Log.")

    async def replace_tasks_from_id(self, user_id: str, start_task_id: int, new_plan_steps: List[str]):
        """
        Replaces a block of tasks starting from a given ID with a new plan.
        """
        start_index = -1
        for i, task in enumerate(self.tasks):
            if task.get('id') == start_task_id:
                start_index = i
                break

        if start_index == -1:
            logger.error(f"Could not find task with ID {start_task_id} to start replacement.")
            return

        self.tasks = self.tasks[:start_index]

        for step in new_plan_steps:
            await self.add_task(user_id=user_id, description=step, notify=False)

        self._save_log_to_disk()
        await self._notify_ui(user_id)
        logger.info(f"Replaced tasks from ID {start_task_id} with new plan of {len(new_plan_steps)} steps.")

    def get_initial_goal(self) -> str:
        """Returns the initial user goal that started the mission."""
        return self._initial_user_goal

    async def update_task(self, user_id: str, task_id: int, description: str) -> bool:
        """Updates the description of a specific task."""
        if not description or not description.strip():
            raise ValueError("Task description cannot be empty.")

        for task in self.tasks:
            if task.get('id') == task_id:
                task['description'] = description
                self._save_log_to_disk()
                await self._notify_ui(user_id)
                logger.info(f"Updated task {task_id} for user {user_id}.")
                return True
        logger.warning(f"Attempted to update non-existent task {task_id} for user {user_id}.")
        return False

    async def delete_task(self, user_id: str, task_id: int) -> bool:
        """Deletes a specific task from the log."""
        task_to_delete = next((task for task in self.tasks if task.get('id') == task_id), None)

        if task_to_delete:
            self.tasks.remove(task_to_delete)
            self._save_log_to_disk()
            await self._notify_ui(user_id)
            logger.info(f"Deleted task {task_id} for user {user_id}.")
            return True

        logger.warning(f"Attempted to delete non-existent task {task_id} for user {user_id}.")
        return False

    async def reorder_tasks(self, user_id: str, ordered_task_ids: List[int]) -> bool:
        """Reorders the entire task list based on a list of IDs."""
        task_map = {task['id']: task for task in self.tasks}

        # Check if all provided IDs are valid and match the current tasks
        if len(ordered_task_ids) != len(self.tasks) or set(ordered_task_ids) != set(task_map.keys()):
            logger.error(f"Task reorder request for user {user_id} has mismatched or invalid IDs.")
            return False

        new_task_list = [task_map[task_id] for task_id in ordered_task_ids if task_id in task_map]

        self.tasks = new_task_list
        self._save_log_to_disk()
        await self._notify_ui(user_id)
        logger.info(f"Reordered tasks for user {user_id}.")
        return True