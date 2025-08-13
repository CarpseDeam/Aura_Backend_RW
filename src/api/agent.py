# src/api/agent.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from src.dependencies import get_aura_services
# --- THIS IS THE FIX ---
# ServiceManager lives in 'managers', DevelopmentTeamService lives in 'services'.
from src.core.managers import ServiceManager, ProjectManager
from src.services import DevelopmentTeamService

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    project_name: str  # The user must specify which project workspace to use


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_agent_plan(
        request: GenerateRequest,
        background_tasks: BackgroundTasks,
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Accepts a user prompt and a project name, then starts the Aura planning
    workflow as a background task within that user's specific project context.
    """
    dev_team: DevelopmentTeamService = aura_services.get_development_team_service()
    project_manager: ProjectManager = aura_services.get_project_manager()

    # Load or create the project for the user
    # Note: The desktop `new_project` creates a timestamped folder. We might want
    # a simpler naming convention for the web.
    project_path = project_manager.load_project(request.project_name)
    if not project_path:
        project_path = project_manager.new_project(request.project_name)

    if not project_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create or load the user project workspace."
        )

    # Add the long-running async function to FastAPI's background tasks.
    # This immediately frees up the server to return a response.
    background_tasks.add_task(
        dev_team.run_aura_planner_workflow,
        user_idea=request.prompt,
        conversation_history=[]  # Placeholder for now
    )

    return {"message": "Aura has received your request and the mission is underway."}