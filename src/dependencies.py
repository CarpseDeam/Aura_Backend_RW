from pathlib import Path
from fastapi import Depends
from src.event_bus import EventBus
from src.core.managers import ProjectManager, ServiceManager

from src.api.auth import get_current_user
from src.db.models import User

# A simple in-memory cache to hold service instances for a user during a single request.
# This is a good practice for more complex scenarios, but for now, it's a placeholder.
_service_cache = {}

def get_aura_services(current_user: User = Depends(get_current_user)) -> ServiceManager:
    """
    Dependency that creates and yields a full, user-specific ServiceManager stack.
    FastAPI will run this for every request that needs it, providing a clean,
    isolated Aura instance for each authenticated user.
    """
    user_id = str(current_user.id)
    print(f"✅ Spinning up dedicated Aura services for user: {current_user.email} ({user_id})")

    # Define the workspace path for this specific user.
    user_workspace_path = Path(f"workspaces/{user_id}")
    user_workspace_path.mkdir(parents=True, exist_ok=True)

    # Instantiate the core components for THIS user.
    event_bus = EventBus()
    # The ProjectManager is now scoped to the user's private workspace.
    project_manager = ProjectManager(event_bus, workspace_path=str(user_workspace_path))

    # We need to adapt the ServiceManager from the desktop app to work in a server context.
    # We will create a slimmed-down, non-GUI version for this.
    # For now, we'll assume the existing one can be used, but we may need to refactor it.
    services = ServiceManager(event_bus, project_root=Path("."))
    services.initialize_core_components(Path("."), project_manager)
    services.initialize_services()

    # NOTE: The desktop ServiceManager has code to launch background servers (LLM server)
    # and GUI windows. In a production web environment, this will be handled differently.
    # For now, we are focusing on getting the core logic wired up.

    print(f"✅ Aura services are online and ready for user {user_id}.")
    return services