from pathlib import Path
from fastapi import Depends
from sqlalchemy.orm import Session
import os
from src.event_bus import EventBus
from src.core.managers import ProjectManager, ServiceManager
from src.db.database import get_db
from src.api.auth import get_current_user
from src.db.models import User
from src.services import (
    MissionLogService, VectorContextService, ToolRunnerService,
    DevelopmentTeamService, ConductorService
)
from src.foundry import FoundryManager
from src.core.llm_client import LLMClient

# --- THE FIX: Create a single, shared FoundryManager instance at startup ---
# This mimics the behavior of the original, working desktop application.
# The tools are now loaded ONCE and shared across all user requests.
foundry_manager = FoundryManager()

def get_foundry_manager() -> FoundryManager:
    """Dependency to provide the shared FoundryManager instance."""
    return foundry_manager

def get_aura_services(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        fm: FoundryManager = Depends(get_foundry_manager) # Inject the shared instance
) -> ServiceManager:
    """
    Dependency that creates and yields a full, user-specific ServiceManager stack.
    THIS IS THE NEW, CORRECTED VERSION. It ensures all services are initialized
    within the same request scope, sharing the same state.
    """
    user_id = str(current_user.id)
    print(f"✅ Spinning up dedicated Aura services for user: {current_user.email} ({user_id})")

    persistent_storage_path = Path("/data")
    user_workspace_path = persistent_storage_path / "workspaces" / user_id

    os.makedirs(user_workspace_path, exist_ok=True)

    event_bus = EventBus()
    project_manager = ProjectManager(event_bus, workspace_path=str(user_workspace_path))
    llm_client = LLMClient()

    # --- Initialize services with shared components ---
    mission_log_service = MissionLogService(project_manager, event_bus)
    vector_context_service = VectorContextService(user_db_session=db, user_id=current_user.id)

    tool_runner_service = ToolRunnerService(
        event_bus=event_bus,
        foundry_manager=fm,
        project_manager=project_manager,
        mission_log_service=mission_log_service,
        vector_context_service=vector_context_service,
        llm_client=llm_client
    )

    development_team_service = DevelopmentTeamService(
        event_bus=event_bus,
        llm_client=llm_client,
        project_manager=project_manager,
        mission_log_service=mission_log_service,
        vector_context_service=vector_context_service,
        foundry_manager=fm,
        db_session=db,
        user_id=current_user.id
    )

    # --- THE NEW ARCHITECTURE: The Conductor is now the primary brain ---
    conductor_service = ConductorService(
        event_bus=event_bus,
        mission_log_service=mission_log_service,
        tool_runner_service=tool_runner_service,
        development_team_service=development_team_service,
        foundry_manager=fm,
        llm_client=llm_client,
        db_session=db
    )

    # --- Assemble the master ServiceManager ---
    services = ServiceManager(event_bus, project_root=Path("."))
    services.project_manager = project_manager
    services.llm_client = llm_client
    services.foundry_manager = fm
    services.mission_log_service = mission_log_service
    services.vector_context_service = vector_context_service
    services.tool_runner_service = tool_runner_service
    services.development_team_service = development_team_service
    services.conductor_service = conductor_service
    services.db = db
    services.user_id = current_user.id

    print(f"✅ Aura services are online and ready for user {user_id}.")
    return services