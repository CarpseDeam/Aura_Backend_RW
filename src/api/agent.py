# agent.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
import traceback
from src.core.websockets import websocket_manager

from src.dependencies import get_aura_services, get_project_manager
from src.core.managers import ServiceManager, ProjectManager
from src.services import DevelopmentTeamService, ConductorService, MissionLogService, VectorContextService
from src.db.models import User
from src.api.auth import get_current_user
from src.db.database import SessionLocal


# --- THE FIX: A more robust wrapper with comprehensive error handling ---
async def run_planner_task_wrapper(
        dev_team_service: DevelopmentTeamService, user_id: int, user_idea: str, history: List[Dict[str, Any]]
):
    """
    This wrapper creates a new DB session specifically for the background task,
    ensuring it doesn't use the closed session from the original request.
    It now includes robust error handling to prevent silent failures.
    """
    db = SessionLocal()
    try:
        # Re-hydrate the service with a live DB session and correct user ID
        dev_team_service.db = db
        dev_team_service.user_id = user_id
        dev_team_service.refresh_llm_assignments() # Load fresh model assignments

        await dev_team_service.run_aura_planner_workflow(
            user_id=str(user_id), user_idea=user_idea, conversation_history=history
        )
    except Exception as e:
        # CRITICAL: This block breaks the silence if the background task fails.
        error_message = f"A critical error occurred while generating the plan: {e}"
        print(f"FATAL ERROR in planner background task for user {user_id}: {e}")
        traceback.print_exc()
        await websocket_manager.broadcast_to_user({
            "type": "system_log", "content": error_message
        }, str(user_id))
    finally:
        db.close()


# --- THE FIX: A more robust wrapper with comprehensive error handling ---
async def run_dispatch_task_wrapper(conductor_service: ConductorService, user_id: int):
    """
    Creates a new DB session and fully re-hydrates the entire service stack
    that the Conductor will use during its long-running execution.
    It now includes robust error handling to prevent silent failures.
    """
    db = SessionLocal()
    try:
        # Re-hydrate all services that will be used in the background loop
        dev_team_service = conductor_service.development_team_service
        dev_team_service.db = db
        dev_team_service.user_id = user_id
        dev_team_service.refresh_llm_assignments() # Load fresh model assignments

        conductor_service.db = db
        conductor_service.user_id = user_id

        tool_runner_service = conductor_service.tool_runner_service
        if tool_runner_service and tool_runner_service.vector_context_service:
            tool_runner_service.vector_context_service.db_session = db
            tool_runner_service.vector_context_service.user_id = user_id

        await conductor_service.execute_mission_in_background(user_id=str(user_id))
    except Exception as e:
        # CRITICAL: This block breaks the silence if the background task fails.
        error_message = f"A critical error occurred during mission execution: {e}"
        print(f"FATAL ERROR in dispatcher background task for user {user_id}: {e}")
        traceback.print_exc()
        await websocket_manager.broadcast_to_user({
            "type": "system_log", "content": error_message
        }, str(user_id))
    finally:
        db.close()

async def run_reindex_task_wrapper(
    vcs: VectorContextService, file_path: Path, content: str
):
    """Wrapper to run the re-indexing task in the background."""
    try:
        await vcs.reindex_file(file_path, content)
    except Exception as e:
        print(f"BACKGROUND RE-INDEXING FAILED for {file_path}: {e}")

# --- NEW: Wrapper for the auto-indexing background task ---
async def run_initial_project_index_wrapper(
    vcs: VectorContextService, project_path: Path
):
    """Wrapper to run the initial, full-project indexing task in the background."""
    print(f"BACKGROUND: Starting initial project index for {project_path}")
    try:
        await vcs.reindex_entire_project()
        print(f"BACKGROUND: Successfully completed initial project index for {project_path}")
    except Exception as e:
        print(f"BACKGROUND INITIAL INDEX FAILED for {project_path}: {e}")


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

class FileWriteRequest(BaseModel):
    path: str
    content: str


@router.post("/chat")
async def agent_chat(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
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
    dev_team: DevelopmentTeamService = aura_services.get_development_team_service()
    project_manager: ProjectManager = aura_services.get_project_manager()
    mission_log_service: MissionLogService = aura_services.mission_log_service

    try:
        project_path = project_manager.load_project(request.project_name)
        if not project_path:
            raise HTTPException(status_code=404, detail=f"Project '{request.project_name}' not found.")

        vcs: VectorContextService = aura_services.vector_context_service
        if vcs:
            vcs.load_for_project(Path(project_path))

        mission_log_service.load_log_for_active_project()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load project: {e}")

    background_tasks.add_task(
        run_planner_task_wrapper,
        dev_team_service=dev_team,
        user_id=current_user.id,
        user_idea=request.prompt,
        history=request.history
    )
    return {"message": "Aura has received your request and is formulating a plan."}


@router.post("/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_agent_mission(
        request: DispatchRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    conductor: ConductorService = aura_services.conductor_service
    project_manager: ProjectManager = aura_services.get_project_manager()
    mission_log_service: MissionLogService = aura_services.mission_log_service

    project_path = project_manager.load_project(request.project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{request.project_name}' not found.")

    vcs: VectorContextService = aura_services.vector_context_service
    if vcs:
        vcs.load_for_project(Path(project_path))

    mission_log_service.load_log_for_active_project()

    background_tasks.add_task(
        run_dispatch_task_wrapper,
        conductor_service=conductor,
        user_id=current_user.id
    )
    return {"message": "Dispatch acknowledged. Aura is now executing the mission plan."}


@router.get("/", response_model=List[str])
async def list_user_projects(
        project_manager: ProjectManager = Depends(get_project_manager)
):
    try:
        return project_manager.list_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {e}")


@router.post("/{project_name}", status_code=status.HTTP_201_CREATED)
async def create_new_project(
        project_name: str,
        project_manager: ProjectManager = Depends(get_project_manager)
):
    try:
        project_path = project_manager.new_project(project_name)
        return {"message": "Project created successfully.", "project_path": project_path}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {e}")

# --- NEW ENDPOINT FOR AUTO-INDEXING ---
@router.post("/{project_name}/load", status_code=status.HTTP_200_OK)
async def load_project_and_auto_index(
    project_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Loads a project and triggers a one-time, automatic background index
    if the project's vector database is empty.
    """
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path_str = project_manager.load_project(project_name)
    if not project_path_str:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    project_path = Path(project_path_str)
    vcs: VectorContextService = aura_services.vector_context_service
    message = f"Project '{project_name}' loaded successfully."

    if vcs:
        vcs.load_for_project(project_path)
        # Check if the collection is empty.
        if vcs.collection and vcs.collection.count() == 0:
            message += " Initial project scan for AI context has been started in the background."
            background_tasks.add_task(
                run_initial_project_index_wrapper,
                vcs=vcs,
                project_path=project_path
            )

    return {"message": message}


@router.delete("/{project_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_project(
        project_name: str,
        project_manager: ProjectManager = Depends(get_project_manager)
):
    try:
        project_manager.delete_project(project_name)
        return None
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {e}")


@router.get("/workspace/{project_name}/files", response_model=List[Dict[str, Any]])
async def get_project_file_tree(
        project_name: str,
        project_manager: ProjectManager = Depends(get_project_manager)
):
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    return project_manager.get_file_tree()


@router.get("/workspace/{project_name}/file")
async def get_project_file_content(
        project_name: str,
        path: str = Query(...),
        project_manager: ProjectManager = Depends(get_project_manager)
):
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    file_content = project_manager.read_file(path)
    if file_content is None:
        raise HTTPException(status_code=404, detail=f"File not found at path: '{path}'.")

    return {"content": file_content}

@router.post("/workspace/{project_name}/file", status_code=status.HTTP_204_NO_CONTENT)
async def write_project_file_content(
    project_name: str,
    request: FileWriteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    aura_services: ServiceManager = Depends(get_aura_services)
):
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path_str = project_manager.load_project(project_name)
    if not project_path_str:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    project_path = Path(project_path_str)

    vcs: VectorContextService = aura_services.vector_context_service
    if vcs:
        vcs.load_for_project(project_path)

    full_file_path_str = project_manager.write_file(request.path, request.content)
    if full_file_path_str is None:
        raise HTTPException(status_code=400, detail="Invalid file path or failed to write file.")

    if vcs:
        background_tasks.add_task(
            run_reindex_task_wrapper,
            vcs=vcs,
            file_path=Path(full_file_path_str),
            content=request.content
        )

    return None