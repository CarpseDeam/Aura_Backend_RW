# src/services/service_manager.py
from __future__ import annotations
import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import traceback
import asyncio
from sqlalchemy.orm import Session

from src.event_bus import EventBus
from src.core.llm_client import LLMClient
from .project_manager import ProjectManager
from src.core.execution_engine import ExecutionEngine
from src.services import (
    ActionService, AppStateService, MissionLogService, DevelopmentTeamService,
    ConductorService, ToolRunnerService, VectorContextService, CodeIntelligenceService
)
from src.foundry import FoundryManager
from src.events import ProjectCreated

if TYPE_CHECKING:
    from .window_manager import WindowManager


class ServiceManager:
    """
    Manages all application services and their dependencies.
    """

    def __init__(self, event_bus: EventBus, project_root: Path):
        self.event_bus = event_bus
        self.project_root = project_root
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None
        self.foundry_manager: FoundryManager = None
        self.db: Session = None
        self.user_id: int = None

        # Core Services
        self.app_state_service: AppStateService = None
        self.action_service: ActionService = None
        self.mission_log_service: MissionLogService = None
        self.development_team_service: DevelopmentTeamService = None
        self.conductor_service: ConductorService = None
        self.tool_runner_service: ToolRunnerService = None
        self.vector_context_service: VectorContextService = None
        self.code_intelligence_service: CodeIntelligenceService = None

        self.llm_server_process: Optional[subprocess.Popen] = None

        # --- THE FIX: This event subscription is the root cause of the double-initialization bug. IT IS REMOVED. ---
        # self.event_bus.subscribe("project_created", self._on_project_activated)

        self.log_to_event_bus("info", "[ServiceManager] Initialized")

    # --- THE FIX: This entire method was causing services to be re-created incorrectly in a web context. IT IS REMOVED. ---
    # def _on_project_activated(self, event: ProjectCreated):
    #     """
    #     Initializes or re-initializes services that depend on an active project.
    #     """
    #     self.log_to_event_bus("info",
    #                           f"Project activated: {event.project_name}. Synchronizing project-specific services.")
    #     project_path = Path(event.project_path)

    #     self.mission_log_service = MissionLogService(self.project_manager, self.event_bus)
    #     self.mission_log_service.load_log_for_active_project()

    #     rag_db_path = project_path / ".rag_db"
    #     self.vector_context_service = VectorContextService(db_path=str(rag_db_path), user_db_session=self.db,
    #                                                        user_id=self.user_id)

    #     self._initialize_tool_runner()

    #     if self.conductor_service:
    #         self.conductor_service.tool_runner_service = self.tool_runner_service
    #         self.conductor_service.mission_log_service = self.mission_log_service
    #         self.log_to_event_bus("info", "ConductorService references updated.")

    #     if self.development_team_service:
    #         self.development_team_service.vector_context_service = self.vector_context_service
    #         self.development_team_service.mission_log_service = self.mission_log_service
    #         self.log_to_event_bus("info", "DevelopmentTeamService references updated.")

    #     self.log_to_event_bus("success", "Project-specific services synchronized.")

    def log_to_event_bus(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ServiceManager", level, message)

    def initialize_core_components(self, project_root: Path, project_manager: ProjectManager):
        self.log_to_event_bus("info", "[ServiceManager] Initializing core components...")
        self.llm_client = LLMClient()
        self.project_manager = project_manager
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.foundry_manager = FoundryManager()
        self.log_to_event_bus("info", "[ServiceManager] Core components initialized")

    def initialize_services(self):
        """Initialize services with proper dependency order."""
        self.log_to_event_bus("info", "[ServiceManager] Initializing services...")

        self.app_state_service = AppStateService(self.event_bus)

        self.mission_log_service = MissionLogService(self.project_manager, self.event_bus)
        self.vector_context_service = None
        self._initialize_tool_runner()

        self.development_team_service = DevelopmentTeamService(self.event_bus, self)
        self.conductor_service = ConductorService(
            self.event_bus,
            self.mission_log_service,
            self.tool_runner_service,
            self.development_team_service
        )
        self.action_service = ActionService(self.event_bus, self, None, None)
        self.log_to_event_bus("info", "[ServiceManager] Services initialized")

    def _initialize_tool_runner(self):
        """Helper to create or update the tool runner with the latest services."""
        self.tool_runner_service = ToolRunnerService(
            event_bus=self.event_bus,
            foundry_manager=self.foundry_manager,
            project_manager=self.project_manager,
            mission_log_service=self.mission_log_service,
            vector_context_service=self.vector_context_service,
            llm_client=self.llm_client
        )
        self.log_to_event_bus("info", "ToolRunnerService has been configured.")

    async def launch_background_servers(self, timeout: int = 15):
        self.log_to_event_bus("info", "Skipping background server launch in web mode.")
        return

    def terminate_background_servers(self):
        self.log_to_event_bus("info", "Skipping background server termination in web mode.")
        return

    async def shutdown(self):
        self.log_to_event_bus("info", "[ServiceManager] Shutting down services...")
        self.terminate_background_servers()
        self.log_to_event_bus("info", "[ServiceManager] Services shutdown complete")

    def get_llm_client(self) -> LLMClient:
        return self.llm_client

    def get_project_manager(self) -> ProjectManager:
        return self.project_manager

    def get_foundry_manager(self) -> FoundryManager:
        return self.foundry_manager

    def get_development_team_service(self) -> DevelopmentTeamService:
        return self.development_team_service

    def is_fully_initialized(self) -> bool:
        return all([self.llm_client, self.project_manager, self.foundry_manager])