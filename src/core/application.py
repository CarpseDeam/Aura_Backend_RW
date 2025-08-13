# src/core/application.py
import asyncio
import sys
from pathlib import Path

from src.event_bus import EventBus
from src.core.managers import (
    ServiceManager,
    WindowManager,
    EventCoordinator,
    WorkflowManager,
    TaskManager,
    ProjectManager
)
from src.services import CommandHandler


class Application:
    """
    Main application class that coordinates all components.
    """

    def __init__(self, project_root: Path):
        """
        Initialize the application with the project root path.

        Args:
            project_root: Root directory for the application's own files.
        """
        self.project_root = project_root
        print(f"[Application] Initializing with project_root: {self.project_root}")

        self.event_bus = EventBus()
        self.project_manager = ProjectManager(self.event_bus)
        self.window_manager = WindowManager(self.event_bus, self.project_manager)
        self.service_manager = ServiceManager(self.event_bus, self.project_root)
        self.task_manager = TaskManager(self.event_bus)
        self.workflow_manager = WorkflowManager(self.event_bus)
        self.event_coordinator = EventCoordinator(self.event_bus)
        self.command_handler: CommandHandler | None = None
        self._initialization_complete = False
        self._connect_events()

    def _connect_events(self):
        """Set up event connections between components."""
        self.event_bus.subscribe("open_code_viewer_requested", self.window_manager.show_code_viewer)
        self.event_bus.subscribe("project_root_selected", self.project_manager.load_project)
        self.event_bus.subscribe("application_shutdown", lambda: asyncio.create_task(self.shutdown()))
        # The command handler will listen for user commands
        self.event_bus.subscribe("user_command_entered", lambda event: self.command_handler.handle(event))


    async def initialize_async(self):
        """Perform async initialization of components."""
        print("[Application] Starting async initialization...")
        try:
            self.service_manager.initialize_core_components(self.project_root, self.project_manager)
            self.service_manager.initialize_services()

            # Launch all background servers
            await self.service_manager.launch_background_servers()

            self.window_manager.initialize_windows(
                self.service_manager.get_llm_client(),
                self.service_manager,
                self.project_root
            )

            # --- Wire up the CommandHandler ---
            controller = self.window_manager.get_main_window().get_controller()
            self.command_handler = CommandHandler(
                foundry_manager=self.service_manager.get_foundry_manager(),
                event_bus=self.event_bus,
                project_manager=self.project_manager,
                display_callback=controller.get_display_callback(),
                output_log_text_fetcher=controller.get_full_chat_text
            )
            controller.wire_up_command_handler(self.command_handler)
            controller.set_project_manager(self.project_manager)
            controller.set_mission_log_service(self.service_manager.mission_log_service)
            # --- End CommandHandler wiring ---

            self.task_manager.set_managers(self.service_manager, self.window_manager)
            self.workflow_manager.set_managers(self.service_manager, self.window_manager, self.task_manager)
            self.event_coordinator.set_managers(self.service_manager, self.window_manager, self.task_manager, self.workflow_manager)
            self.event_coordinator.wire_all_events()
            self._initialization_complete = True
            print("[Application] Async initialization complete")
        except Exception as e:
            print(f"[Application] CRITICAL ERROR during initialization: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            raise

    def show(self):
        self.window_manager.show_main_window()
        self.event_bus.emit("show_mission_log_requested")

    async def shutdown(self):
        print("[Application] Shutting down application components...")
        if self.task_manager:
            await self.task_manager.cancel_all_tasks()
        if self.service_manager:
            await self.service_manager.shutdown()
        print("[Application] All components shut down.")

    def is_fully_initialized(self) -> bool:
        return (self._initialization_complete and
                self.service_manager.is_fully_initialized() and
                self.window_manager.is_fully_initialized())