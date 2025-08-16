from pathlib import Path
from fastapi import Depends
from sqlalchemy.orm import Session
from src.event_bus import EventBus
from src.core.managers import ProjectManager, ServiceManager
from src.db.database import get_db
from src.api.auth import get_current_user
from src.db.models import User


def get_aura_services(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
) -> ServiceManager:
    """
    Dependency that creates and yields a full, user-specific ServiceManager stack.
    """
    user_id = str(current_user.id)
    print(f"✅ Spinning up dedicated Aura services for user: {current_user.email} ({user_id})")

    # --- THIS IS THE FIX ---
    # This absolute path MUST match your new Railway Volume's Mount Path.
    persistent_storage_path = Path("/data")
    user_workspace_path = persistent_storage_path / "workspaces" / user_id
    user_workspace_path.mkdir(parents=True, exist_ok=True)

    event_bus = EventBus()
    project_manager = ProjectManager(event_bus, workspace_path=str(user_workspace_path))

    services = ServiceManager(event_bus, project_root=Path("."))

    services.db = db
    services.user_id = current_user.id  # Pass the user ID to the service manager

    services.initialize_core_components(Path("."), project_manager)
    services.initialize_services()

    print(f"✅ Aura services are online and ready for user {user_id}.")
    return services