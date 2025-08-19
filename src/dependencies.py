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
    THIS IS THE NEW, REFACTORED VERSION. It is simpler and more robust.
    """
    user_id = str(current_user.id)
    print(f"✅ Spinning up dedicated Aura services for user: {current_user.email} ({user_id})")

    # --- Step 1: Create the foundational managers and clients ---
    persistent_storage_path = Path("/data")
    user_workspace_path = persistent_storage_path / "workspaces" / user_id
    os.makedirs(user_workspace_path, exist_ok=True)

    event_bus = EventBus()
    project_manager = ProjectManager(event_bus, workspace_path=str(user_workspace_path))
    llm_client = LLMClient()

    # --- Step 2: Assemble the master ServiceManager ---
    # This manager will now be the single source of truth for all other services.
    services = ServiceManager(event_bus, project_root=Path("."))
    services.project_manager = project_manager
    services.llm_client = llm_client
    services.foundry_manager = fm
    services.db = db
    services.user_id = current_user.id

    # --- Step 3: Initialize services, passing the manager for dependency resolution ---
    # This is much cleaner than passing a long list of individual services.
    services.mission_log_service = MissionLogService(project_manager, event_bus)
    services.vector_context_service = VectorContextService(user_db_session=db, user_id=current_user.id)
    services.tool_runner_service = ToolRunnerService(event_bus, services)
    services.development_team_service = DevelopmentTeamService(event_bus, services)
    services.conductor_service = ConductorService(event_bus, services)

    print(f"✅ Aura services are online and ready for user {user_id}.")
    return services