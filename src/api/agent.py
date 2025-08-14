# src/api/agent.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any

from src.dependencies import get_aura_services
from src.core.managers import ServiceManager, ProjectManager
from src.services import DevelopmentTeamService, ConductorService
from src.db.models import User
from src.api.auth import get_current_user

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    project_name: str


class DispatchRequest(BaseModel):
    project_name: str


class ChatRequest(BaseModel):
    prompt: str
    history: List[Dict[str, Any]]


@router.post("/chat")
async def agent_chat(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Handles conversational, non-planning chat with Aura's companion persona.
    """
    dev_team: DevelopmentTeamService = aura_services.get_development_team_service()

    response_text = await dev_team.run_companion_chat(
        user_id=str(current_user.id),
        user_prompt=request.prompt,
        conversation_history=request.history
    )
    return {"reply": response_text}


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_agent_plan(
        request: GenerateRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Accepts a user prompt and project name, starts the Aura planning workflow.
    """
    dev_team: DevelopmentTeamService = aura_services.get_development_team_service()
    project_manager: ProjectManager = aura_services.get_project_manager()

    try:
        project_path = project_manager.load_project(request.project_name)
        if not project_path:
            project_path = project_manager.new_project(request.project_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create or load project: {e}"
        )

    if not project_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create or load the user project workspace."
        )

    user_id = str(current_user.id)
    background_tasks.add_task(
        dev_team.run_aura_planner_workflow,
        user_id=user_id,
        user_idea=request.prompt,
        conversation_history=[]
    )

    return {"message": "Aura has received your request and is formulating a plan."}


@router.post("/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_agent_mission(
        request: DispatchRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Starts the Conductor's autonomous execution loop for a given project.
    """
    conductor: ConductorService = aura_services.conductor_service
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path = project_manager.load_project(request.project_name)
    if not project_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{request.project_name}' not found for this user."
        )
    user_id = str(current_user.id)
    background_tasks.add_task(
        conductor.execute_mission_in_background,
        user_id=user_id
    )
    return {"message": "Dispatch acknowledged. Aura is now executing the mission plan."}