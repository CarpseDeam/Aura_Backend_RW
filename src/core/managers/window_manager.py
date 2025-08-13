# src/core/managers/window_manager.py
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.llm_client import LLMClient
from src.event_bus import EventBus
from src.core.app_state import AppState
from src.events import StreamCodeChunk

if TYPE_CHECKING:
    from .project_manager import ProjectManager
    from .service_manager import ServiceManager


class WindowManager:
    """
    Creates and manages all GUI windows.
    Single responsibility: Window lifecycle and access management.
    NOTE: This class is part of the desktop application's architecture
    and will not be actively used in the server-only backend. It is kept
    for code completeness during the transition.
    """

    def __init__(self, event_bus: EventBus, project_manager: "ProjectManager"):
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.service_manager: "ServiceManager" = None

        # Main windows
        self.main_window = None # No AuraMainWindow on server
        self.code_viewer = None # No CodeViewerWindow on server
        self.log_viewer = None # No LogViewerWindow on server
        self.mission_log_window = None # No MissionLogWindow on server

        # Dialogs
        self.model_config_dialog = None # No ModelConfigurationDialog on server

        print("[WindowManager] Initialized (Server Mode - No GUI will be created)")

    def initialize_windows(self, llm_client: LLMClient, service_manager: "ServiceManager", project_root: Path):
        """Initialize all GUI windows."""
        print("[WindowManager] Skipping window initialization in server mode.")
        pass

    def handle_code_stream(self, event: StreamCodeChunk):
        """Handles a stream_code_chunk event by updating the code viewer."""
        # This logic is now handled by the frontend, which receives WebSocket messages.
        pass

    def handle_app_state_change(self, new_state: AppState, project_name: str | None):
        """
        Listens for global state changes and updates all relevant UI components.
        """
        # No UI components to update on the server.
        pass

    # --- Window Getters ---
    def get_main_window(self):
        return self.main_window

    def get_code_viewer(self):
        return self.code_viewer

    # --- Show Window Methods ---
    def show_main_window(self):
        pass

    def show_mission_log(self, event=None):
        pass

    def _position_side_windows(self):
        pass

    def show_code_viewer(self):
        pass

    async def show_model_config_dialog(self):
        pass

    def show_log_viewer(self):
        pass

    # --- UI Update Methods ---
    def update_project_display(self, project_name: str):
        pass

    def prepare_code_viewer_for_new_project(self):
        pass

    def load_project_in_code_viewer(self, project_path: str):
        pass

    def is_fully_initialized(self) -> bool:
        # In server mode, this manager is "initialized" by default.
        return True