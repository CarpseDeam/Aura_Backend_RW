# src/dependencies.py
from pathlib import Path
from fastapi import Depends
from sqlalchemy.orm import Session
import os
from src.event_bus import EventBus
from src.core.managers import ProjectManager, ServiceManager
from src.db.database import get_db, SessionLocal
from src.api.auth import get_current_user
from src.db import models, crud
from src.db.models import User
from src.services import (
    MissionLogService, VectorContextService, ToolRunnerService,
    DevelopmentTeamService, ConductorService
)
from src.foundry import FoundryManager
from src.core.llm_client import LLMClient

foundry_manager = FoundryManager()

def get_foundry_manager() -> FoundryManager:
    """Dependency to provide the shared FoundryManager instance."""
    return foundry_manager

def get_project_manager(
    current_user: User = Depends(get_current_user)
) -> ProjectManager:
    user_id = str(current_user.id)
    persistent_storage_path = Path("/data")
    user_workspace_path = persistent_storage_path / "workspaces" / user_id
    os.makedirs(user_workspace_path, exist_ok=True)
    return ProjectManager(EventBus(), workspace_path=str(user_workspace_path))


def get_aura_services(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        fm: FoundryManager = Depends(get_foundry_manager)
) -> ServiceManager:
    user_id = str(current_user.id)
    print(f"✅ Spinning up dedicated Aura services for user: {current_user.email} ({user_id})")

    persistent_storage_path = Path("/data")
    user_workspace_path = persistent_storage_path / "workspaces" / user_id
    os.makedirs(user_workspace_path, exist_ok=True)

    event_bus = EventBus()
    project_manager = ProjectManager(event_bus, workspace_path=str(user_workspace_path))
    llm_client = LLMClient()

    assignments_from_db = crud.get_assignments_for_user(db, user_id=current_user.id)
    if assignments_from_db:
        llm_client.set_assignments({a.role_name: a.model_id for a in assignments_from_db})
        llm_client.set_temperatures({a.role_name: a.temperature for a in assignments_from_db})
        print(f"✅ LLM client pre-populated for user {current_user.id} with {len(assignments_from_db)} assignments.")

    services = ServiceManager(event_bus, project_root=Path("."))
    services.project_manager = project_manager
    services.llm_client = llm_client
    services.foundry_manager = fm
    services.db = db
    services.user_id = current_user.id

    services.mission_log_service = MissionLogService(project_manager, event_bus)
    services.vector_context_service = VectorContextService()
    services.tool_runner_service = ToolRunnerService(event_bus, services)
    services.development_team_service = DevelopmentTeamService(event_bus, services)
    services.conductor_service = ConductorService(event_bus, services)

    print(f"✅ Aura services are online and ready for user {user_id}.")
    return services

def rehydrate_services_for_background_task(services: ServiceManager, user_id: int) -> Session:
    """
    Takes a ServiceManager instance, creates a new DB session, and injects it
    into the manager to ensure all downstream services use the live session.
    """
    db = SessionLocal()
    services.db = db
    services.user_id = user_id

    # The only other action required is to refresh the LLM settings, as they
    # are the only stateful part of the system that depends on the database.
    if services.development_team_service:
        services.development_team_service.refresh_llm_assignments()

    print(f"🔄 Services re-hydrated for background task for user {user_id}.")
    return db