# src/core/managers/event_coordinator.py
import asyncio
from src.event_bus import EventBus
from src.core.managers.service_manager import ServiceManager
from src.core.managers.window_manager import WindowManager
from src.core.managers.task_manager import TaskManager
from src.core.managers.workflow_manager import WorkflowManager
# This service lives in the 'services' package, not with the managers.
from src.services import AppStateService


class EventCoordinator:
    """
    Coordinates events between different components of the application.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.service_manager: ServiceManager = None
        self.window_manager: WindowManager = None
        self.task_manager: TaskManager = None
        self.workflow_manager: WorkflowManager = None
        print("[EventCoordinator] Initialized")

    def set_managers(self, service_manager: ServiceManager, window_manager: WindowManager, task_manager: TaskManager,
                     workflow_manager: WorkflowManager):
        self.service_manager = service_manager
        self.window_manager = window_manager
        self.task_manager = task_manager
        self.workflow_manager = workflow_manager

    def wire_all_events(self):
        """Wire all events between components."""
        print("[EventCoordinator] Wiring all events...")
        self._wire_ui_events()
        self._wire_ai_workflow_events()
        self._wire_execution_events()
        self._wire_chat_session_events()
        self._wire_status_bar_events()
        self._wire_foundry_events()
        print("[EventCoordinator] All events wired successfully.")

    def _wire_status_bar_events(self):
        """
        This method is now a no-op as the StatusBarWidget has been removed.
        Kept for structural consistency.
        """
        pass

    def _wire_chat_session_events(self):
        # This can be implemented later if needed
        pass

    def _wire_ui_events(self):
        action_service = self.service_manager.action_service
        if action_service:
            self.event_bus.subscribe("new_project_requested", action_service.handle_new_project)
            self.event_bus.subscribe("load_project_requested", action_service.handle_load_project)
            self.event_bus.subscribe("new_session_requested", action_service.handle_new_session)

        if self.window_manager:
            self.event_bus.subscribe("app_state_changed", self.window_manager.handle_app_state_change)

        self.event_bus.subscribe(
            "configure_models_requested",
            lambda: asyncio.create_task(self.window_manager.show_model_config_dialog())
        )

        self.event_bus.subscribe("show_log_viewer_requested", self.window_manager.show_log_viewer)
        self.event_bus.subscribe("show_mission_log_requested", self.window_manager.show_mission_log)

    def _wire_ai_workflow_events(self):
        if self.workflow_manager:
            self.event_bus.subscribe("user_request_submitted", self.workflow_manager.handle_user_request)

        conductor_service = self.service_manager.conductor_service
        if conductor_service:
            self.event_bus.subscribe("mission_dispatch_requested", conductor_service.execute_mission_in_background)

    def _wire_execution_events(self):
        # Handled by services directly
        pass

    def _wire_foundry_events(self):
        """Connects events related to the tool system."""
        foundry_manager = self.service_manager.get_foundry_manager()
        if foundry_manager:
            self.event_bus.subscribe("tools_modified", foundry_manager.handle_tools_modified)