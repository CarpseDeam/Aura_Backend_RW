# src/core/managers/service_manager.py
from __future__ import annotations
import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional
import traceback
import asyncio

from src.event_bus import EventBus
from src.core.llm_client import LLMClient
from .project_manager import ProjectManager
from src.core.execution_engine import ExecutionEngine
from src.services import (
    ActionService, AppStateService, MissionLogService, DevelopmentTeamService,
    ConductorService, ToolRunnerService, VectorContextService
)
from src.foundry import FoundryManager
from src.events import ProjectCreated

if TYPE_CHECKING:
    from .window_manager import WindowManager


class ServiceManager:
    """
    Manages all application services and their dependencies.
    Single responsibility: Service lifecycle and dependency injection.
    """

    def __init__(self, event_bus: EventBus, project_root: Path):
        self.event_bus = event_bus
        self.project_root = project_root
        self.llm_client: LLMClient = None
        self.project_manager: ProjectManager = None
        self.execution_engine: ExecutionEngine = None
        self.foundry_manager: FoundryManager = None

        # Core Services
        self.app_state_service: AppStateService = None
        self.action_service: ActionService = None
        self.mission_log_service: MissionLogService = None
        self.development_team_service: DevelopmentTeamService = None
        self.conductor_service: ConductorService = None
        self.tool_runner_service: ToolRunnerService = None
        self.vector_context_service: VectorContextService = None

        self.llm_server_process: Optional[subprocess.Popen] = None
        self.event_bus.subscribe("project_created", self._on_project_activated)

        self.log_to_event_bus("info", "[ServiceManager] Initialized")

    def _on_project_activated(self, event: ProjectCreated):
        """
        Initializes or re-initializes services that depend on an active project.
        This is the central point for ensuring all services are synced after a
        project change.
        """
        self.log_to_event_bus("info",
                              f"Project activated: {event.project_name}. Synchronizing project-specific services.")
        project_path = Path(event.project_path)

        # 1. Create a new Mission Log service for the new project context.
        self.mission_log_service = MissionLogService(self.project_manager, self.event_bus)
        self.mission_log_service.load_log_for_active_project()

        # 2. Create the RAG database service for the new project context.
        rag_db_path = project_path / ".rag_db"
        self.vector_context_service = VectorContextService(db_path=str(rag_db_path))

        # 3. Create a new Tool Runner with the new services.
        self._initialize_tool_runner()

        # 4. *** THE FIX IS HERE: ***
        # Ensure all major services are updated with the NEW instances of the services
        # they depend on, guaranteeing everyone is using the same objects.
        if self.conductor_service:
            self.conductor_service.tool_runner_service = self.tool_runner_service
            self.conductor_service.mission_log_service = self.mission_log_service
            self.log_to_event_bus("info", "ConductorService references updated.")

        if self.development_team_service:
            self.development_team_service.vector_context_service = self.vector_context_service
            self.development_team_service.mission_log_service = self.mission_log_service
            self.log_to_event_bus("info", "DevelopmentTeamService references updated.")

        self.log_to_event_bus("success", "Project-specific services synchronized.")

    def log_to_event_bus(self, level: str, message: str):
        self.event_bus.emit("log_message_received", "ServiceManager", level, message)

    def initialize_core_components(self, project_root: Path, project_manager: ProjectManager):
        self.log_to_event_bus("info", "[ServiceManager] Initializing core components...")
        self.llm_client = LLMClient(project_root)
        self.project_manager = project_manager
        self.execution_engine = ExecutionEngine(self.project_manager)
        self.foundry_manager = FoundryManager()
        self.log_to_event_bus("info", "[ServiceManager] Core components initialized")

    def initialize_services(self):
        """Initialize services with proper dependency order."""
        self.log_to_event_bus("info", "[ServiceManager] Initializing services...")

        self.app_state_service = AppStateService(self.event_bus)

        # Services that get re-created when a project is activated
        self.mission_log_service = MissionLogService(self.project_manager, self.event_bus)
        self.vector_context_service = None  # Will be created on project activation
        self._initialize_tool_runner()

        # Services that persist
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
            llm_client=self.llm_client  # This line was missing
        )
        self.log_to_event_bus("info", "ToolRunnerService has been configured.")

    async def launch_background_servers(self, timeout: int = 15):
        python_executable_to_use: str
        cwd_for_servers: Path
        log_dir_for_servers: Path

        self.log_to_event_bus("info", "Determining paths for launching background servers...")

        server_script_base_dir = self.project_root / "servers"
        python_executable_to_use = sys.executable
        cwd_for_servers = self.project_root
        log_dir_for_servers = self.project_root

        llm_script_path = server_script_base_dir / "llm_server.py"
        llm_subprocess_log_file = log_dir_for_servers / "llm_server_subprocess.log"

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        if self.llm_server_process is None or self.llm_server_process.poll() is not None:
            self.log_to_event_bus("info", f"Attempting to launch LLM server from {llm_script_path}...")
            try:
                with open(llm_subprocess_log_file, "w", encoding="utf-8") as llm_log_handle:
                    self.llm_server_process = subprocess.Popen(
                        [python_executable_to_use, str(llm_script_path)], cwd=str(cwd_for_servers),
                        stdout=llm_log_handle, stderr=subprocess.STDOUT, startupinfo=startupinfo
                    )
                self.log_to_event_bus("info", f"LLM Server process started with PID: {self.llm_server_process.pid}")
            except Exception as e:
                self.log_to_event_bus("error", f"Failed to launch LLM server: {e}\n{traceback.format_exc()}")

        self.log_to_event_bus("info", "Waiting for LLM server to become available...")
        start_time = asyncio.get_event_loop().time()
        server_ready = False
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                models = await self.llm_client.get_available_models()
                if models:
                    self.log_to_event_bus("success",
                                          f"LLM Server is online. Found models from providers: {list(models.keys())}")
                    server_ready = True
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        if not server_ready:
            msg = f"LLM Server failed to start within {timeout} seconds. Check llm_server_subprocess.log for errors."
            self.log_to_event_bus("error", msg)
            raise RuntimeError(msg)

    def terminate_background_servers(self):
        self.log_to_event_bus("info", "[ServiceManager] Terminating background servers...")
        servers = {"LLM": self.llm_server_process}
        for name, process in servers.items():
            if process and process.poll() is None:
                self.log_to_event_bus("info", f"[ServiceManager] Terminating {name} server (PID: {process.pid})...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    self.log_to_event_bus("info", f"[ServiceManager] {name} server terminated.")
                except subprocess.TimeoutExpired:
                    self.log_to_event_bus("warning",
                                          f"[ServiceManager] {name} server did not terminate gracefully. Killing.")
                    process.kill()

        self.llm_server_process = None

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