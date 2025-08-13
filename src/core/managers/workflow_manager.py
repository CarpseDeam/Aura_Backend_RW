# src/core/managers/workflow_manager.py
from typing import Optional, Dict

from src.event_bus import EventBus
from src.core.app_state import AppState
from src.core.managers.service_manager import ServiceManager
from src.core.managers.window_manager import WindowManager
from src.core.managers.task_manager import TaskManager
from src.events import UserPromptEntered, PostChatMessage


class WorkflowManager:
    """
    Orchestrates AI workflows based on the authoritative application state.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager: ServiceManager = None
        self.window_manager: WindowManager = None
        self.task_manager: TaskManager = None
        print("[WorkflowManager] Initialized")

    def set_managers(self, service_manager: ServiceManager, window_manager: WindowManager, task_manager: TaskManager):
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager

    def handle_user_request(self, event: UserPromptEntered):
        """
        The central router for all user chat input.
        This workflow always interprets user input as a request to create a high-level plan.
        """
        prompt = event.prompt_text
        if not prompt.strip() and not event.image_bytes:
            return

        dev_team_service = self.service_manager.get_development_team_service()

        # The user's prompt is a direct instruction to have Aura create a plan.
        workflow_coroutine = dev_team_service.run_aura_planner_workflow(
            user_idea=prompt,
            conversation_history=event.conversation_history
        )

        if workflow_coroutine:
            self.task_manager.start_ai_workflow_task(workflow_coroutine)

    def log(self, level, message):
        self.event_bus.emit("log_message_received", "WorkflowManager", level, message)