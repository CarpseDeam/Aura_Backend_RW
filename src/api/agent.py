# src/api/agent.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Dict, Any

from src.dependencies import get_aura_services
from src.core.managers import ServiceManager, ProjectManager
from src.services import DevelopmentTeamService, ConductorService
from src.db.models import User
from src.api.auth import get_current_user

router = APIRouter(
    prefix="/projects",
    tags=["Project Management"]
)


class GenerateRequest(BaseModel):
    prompt: str
    project_name: str
    history: List[Dict[str, Any]]


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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{request.project_name}' not found. Cannot generate plan."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load project: {e}"
        )

    user_id = str(current_user.id)
    background_tasks.add_task(
        dev_team.run_aura_planner_workflow,
        user_id=user_id,
        user_idea=request.prompt,
        conversation_history=request.history
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


@router.get("/", response_model=List[str])
async def list_user_projects(
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """Lists all project names for the current user."""
    project_manager: ProjectManager = aura_services.get_project_manager()
    try:
        return project_manager.list_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {e}")


@router.post("/{project_name}", status_code=status.HTTP_201_CREATED)
async def create_new_project(
        project_name: str,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """Creates a new, empty project workspace for the user."""
    project_manager: ProjectManager = aura_services.get_project_manager()
    try:
        project_path = project_manager.new_project(project_name)
        return {"message": "Project created successfully.", "project_path": project_path}
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create project: {e}")


@router.delete("/{project_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_project(
        project_name: str,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """Deletes an existing project workspace for the user."""
    project_manager: ProjectManager = aura_services.get_project_manager()
    try:
        project_manager.delete_project(project_name)
        return None
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e: # For safety violations
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete project: {e}")


@router.get("/workspace/{project_name}/files", response_model=List[Dict[str, Any]])
async def get_project_file_tree(
        project_name: str,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Retrieves the file and folder structure for a given project.
    """
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    return project_manager.get_file_tree()


@router.get("/workspace/{project_name}/file")
async def get_project_file_content(
        project_name: str,
        path: str = Query(...),
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Retrieves the content of a specific file within a project.
    """
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    file_content = project_manager.read_file(path)
    if file_content is None:
        raise HTTPException(status_code=404, detail=f"File not found at path: '{path}'.")

    return {"content": file_content}