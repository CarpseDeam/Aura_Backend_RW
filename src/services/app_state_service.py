# src/services/app_state_service.py
from src.event_bus import EventBus
from src.core.app_state import AppState


class AppStateService:
    """
    A centralized service to manage the application's global state.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._app_state: AppState = AppState.BOOTSTRAP
        print("[AppStateService] Initialized.")

    def get_app_state(self) -> AppState:
        return self._app_state

    def set_app_state(self, new_state: AppState, project_name: str | None = None):
        if self._app_state != new_state:
            self._app_state = new_state
            self.log("info", f"Application state changed to: {new_state.name}")
            self.event_bus.emit("app_state_changed", new_state, project_name)

    def log(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "AppStateService", level, message)