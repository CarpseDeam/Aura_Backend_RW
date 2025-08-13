# src/services/mission_log_service.py
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.event_bus import EventBus
from src.events import MissionLogUpdated, ProjectCreated

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
        self.event_bus.subscribe("project_created", self.handle_project_created)
        logger.info("MissionLogService initialized.")

    def handle_project_created(self, event: ProjectCreated):
        """Resets and loads the log when a new project becomes active."""
        logger.info(f"ProjectCreated event received. Resetting and loading mission log for '{event.project_name}'.")
        self.load_log_for_active_project()

    def _get_log_path(self) -> Optional[Path]:
        """Gets the path to the mission log file for the active project."""
        if self.project_manager.active_project_path:
            return self.project_manager.active_project_path / MISSION_LOG_FILENAME
        return None

    def _save_and_notify(self):
        """Saves the current list of tasks to disk and notifies the UI."""
        data_to_save = {
            "initial_goal": self._initial_user_goal,
            "tasks": self.tasks
        }
        self.event_bus.emit("mission_log_updated", MissionLogUpdated(tasks=self.get_tasks()))
        logger.debug(f"UI notified of mission log update. Task count: {len(self.tasks)}")

        log_path = self._get_log_path()
        if not log_path:
            return

        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2)
            logger.debug(f"Mission Log saved to disk at {log_path}.")
        except IOError as e:
            logger.error(f"Failed to save mission log to {log_path}: {e}")

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
        self._save_and_notify()

    def set_initial_plan(self, plan_steps: List[str], user_goal: str):
        """Clears all tasks and sets a new plan, storing the original user goal."""
        self.tasks = []
        self._next_task_id = 1
        self._initial_user_goal = user_goal

        self.add_task(
            description="Index the project to build a contextual map.",
            tool_call={"tool_name": "index_project_context", "arguments": {"path": "."}},
            notify=False
        )

        for step in plan_steps:
            self.add_task(description=step, notify=False)
        self._save_and_notify()
        logger.info(f"Initial plan with {len(self.tasks)} steps has been set.")

    def add_task(self, description: str, tool_call: Optional[Dict] = None, notify: bool = True) -> Dict[str, Any]:
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
        if notify:
            self._save_and_notify()
        return new_task

    def mark_task_as_done(self, task_id: int) -> bool:
        """Marks a specific task as completed."""
        for task in self.tasks:
            if task.get('id') == task_id:
                if not task.get('done'):
                    task['done'] = True
                    task['last_error'] = None # Clear error on success
                    self._save_and_notify()
                    logger.info(f"Marked task {task_id} as done.")
                return True
        logger.warning(f"Attempted to mark non-existent task {task_id} as done.")
        return False

    def get_tasks(self, done: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Returns a copy of the current tasks, optionally filtered by done status."""
        if done is None:
            return list(self.tasks)
        return [task for task in self.tasks if task.get('done') == done]

    def clear_all_tasks(self):
        """Removes all tasks from the log."""
        if self.tasks:
            self.tasks = []
            self._next_task_id = 1
            self._initial_user_goal = ""
            self._save_and_notify()
            logger.info("All tasks cleared from the Mission Log.")

    def replace_tasks_from_id(self, start_task_id: int, new_plan_steps: List[str]):
        """
        Replaces a block of tasks starting from a given ID with a new plan.
        The failed task and all subsequent tasks are removed.
        """
        start_index = -1
        for i, task in enumerate(self.tasks):
            if task.get('id') == start_task_id:
                start_index = i
                break

        if start_index == -1:
            logger.error(f"Could not find task with ID {start_task_id} to start replacement.")
            return

        # Remove the failed task and all subsequent tasks
        self.tasks = self.tasks[:start_index]

        # Add the new plan steps
        for step in new_plan_steps:
            self.add_task(description=step, notify=False)

        self._save_and_notify()
        logger.info(f"Replaced tasks from ID {start_task_id} with new plan of {len(new_plan_steps)} steps.")

    def get_initial_goal(self) -> str:
        """Returns the initial user goal that started the mission."""
        return self._initial_user_goal