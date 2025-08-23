# src/api/agent.py
import logging
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query, Response

from typing import List, Dict, Any
from pathlib import Path
import traceback
import functools

from pydantic import BaseModel

from src.core.websockets import websocket_manager
from src.services import mission_control
from src.dependencies import get_aura_services, rehydrate_services_for_background_task
from src.core.managers import ServiceManager, ProjectManager
from src.services import DevelopmentTeamService, ConductorService, MissionLogService, VectorContextService
from src.db.models import User
from src.api.auth import get_current_user

# Initialize logger
logger = logging.getLogger(__name__)


def background_task_handler(send_idle_status: bool = False, error_message_prefix: str = "An error occurred in a background task"):
    """
    A decorator to handle setup, teardown, and error reporting for background tasks.
    It rehydrates services, closes the DB session, and logs errors.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            services = kwargs.get('services')
            user_id = kwargs.get('user_id')
            if not services or not user_id:
                logger.fatal("FATAL: 'services' and 'user_id' must be provided as keyword arguments to the background task.")
                return

            db = None
            try:
                db = rehydrate_services_for_background_task(services, user_id)
                await func(*args, **kwargs)
            except Exception as e:
                error_message = f"{error_message_prefix}: {e}"
                logger.fatal(f"FATAL ERROR in background task for user {user_id}: {e}", exc_info=True)
                if send_idle_status:
                    await websocket_manager.broadcast_to_user({
                        "type": "system_log", "content": error_message
                    }, str(user_id))
            finally:
                if db:
                    db.close()
                if send_idle_status:
                    await websocket_manager.broadcast_to_user({"type": "agent_status", "status": "idle"}, str(user_id))
        return wrapper
    return decorator


@background_task_handler(send_idle_status=True, error_message_prefix="A critical error occurred while generating the plan")
async def run_planner_task(
        services: ServiceManager, user_id: int, project_name: str, user_idea: str, history: List[Dict[str, Any]], **kwargs
):
    """Background task to run the Aura planner workflow."""
    project_path_str = services.project_manager.load_project(project_name)
    services.mission_log_service.load_log_for_active_project()

    vcs: VectorContextService = services.vector_context_service
    if vcs and project_path_str:
        vcs.load_for_project(Path(project_path_str), user_id)

    await services.development_team_service.run_aura_planner_workflow(
        user_id=str(user_id), user_idea=user_idea, conversation_history=history, project_name=project_name
    )


@background_task_handler(send_idle_status=True, error_message_prefix="A critical error occurred during mission execution")
async def run_dispatch_task(services: ServiceManager, user_id: int, project_name: str, **kwargs):
    """Background task to run the mission dispatcher."""
    project_path_str = services.project_manager.load_project(project_name)
    services.mission_log_service.load_log_for_active_project()

    vcs: VectorContextService = services.vector_context_service
    if vcs and project_path_str:
        vcs.load_for_project(Path(project_path_str), user_id)

    await services.conductor_service.execute_mission_in_background(user_id=str(user_id))


@background_task_handler(error_message_prefix="Background re-indexing failed")
async def run_reindex_task(
        services: ServiceManager, user_id: int, project_name: str, file_path_str: str, content: str, **kwargs
):
    """Wrapper to run the re-indexing task in the background."""
    project_path_str = services.project_manager.load_project(project_name)
    vcs: VectorContextService = services.vector_context_service
    if vcs and project_path_str:
        vcs.load_for_project(Path(project_path_str), user_id)
        await vcs.reindex_file(Path(file_path_str), content)


@background_task_handler(error_message_prefix="Background initial index failed")
async def run_initial_project_index(
        services: ServiceManager, user_id: int, project_name: str, **kwargs
):
    """Wrapper to run the initial, full-project indexing task in the background."""
    logger.info(f"BACKGROUND: Starting initial project index for {project_name}")
    project_path_str = services.project_manager.load_project(project_name)
    vcs: VectorContextService = services.vector_context_service
    if vcs and project_path_str:
        vcs.load_for_project(Path(project_path_str), user_id)
        await vcs.reindex_entire_project()
        logger.info(f"BACKGROUND: Successfully completed initial project index for {project_name}")


router = APIRouter(
    prefix="/projects",
    tags=["Project Management"]
)


class DispatchRequest(BaseModel):
    project_name: str


class PromptRequest(BaseModel):
    prompt: str
    history: List[Dict[str, Any]]


class FileWriteRequest(BaseModel):
    path: str
    content: str

@router.post("/{project_name}/prompt", status_code=status.HTTP_202_ACCEPTED)
async def handle_agent_prompt(
        project_name: str,
        request: PromptRequest,
        background_tasks: BackgroundTasks,
        response: Response,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    """
    Handles a user prompt by first determining the intent (plan vs. chat)
    and then routing to the appropriate service.
    """
    # 1. Load project context (needed for both chat and plan)
    project_manager: ProjectManager = aura_services.project_manager
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    vcs: VectorContextService = aura_services.vector_context_service
    if vcs:
        vcs.load_for_project(Path(project_path), current_user.id)
    aura_services.mission_log_service.load_log_for_active_project()

    # 2. Determine intent
    dev_team: DevelopmentTeamService = aura_services.development_team_service
    intent = await dev_team.determine_user_intent(
        user_id=str(current_user.id),
        user_prompt=request.prompt,
        conversation_history=request.history
    )

    # 3. Route based on intent
    if intent == "PLAN":
        # Use existing background task runner for planning
        background_tasks.add_task(
            run_planner_task,
            services=aura_services,
            user_id=current_user.id,
            project_name=project_name,
            user_idea=request.prompt,
            history=request.history
        )
        return {"message": "Aura has received your request and is formulating a plan."}

    elif intent == "CHAT":
        # Run chat in the foreground. It streams via websocket.
        await dev_team.run_companion_chat(
            user_id=str(current_user.id),
            user_prompt=request.prompt,
            conversation_history=request.history
        )
        response.status_code = status.HTTP_200_OK
        return {"message": "Chat response is being streamed via WebSocket."}

    else:  # Fallback/Error
        logger.error(f"Intent detection failed for user {current_user.id}. Got unexpected intent: '{intent}'")
        # Fallback to chat behavior as it's safer.
        await dev_team.run_companion_chat(
            user_id=str(current_user.id),
            user_prompt=request.prompt,
            conversation_history=request.history
        )
        response.status_code = status.HTTP_200_OK
        return {"message": "Could not determine intent, defaulting to chat. Response is being streamed via WebSocket."}

@router.post("/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch_agent_mission(
        request: DispatchRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    # No need to load project here; the background task will handle it.
    background_tasks.add_task(
        run_dispatch_task,
        services=aura_services,
        user_id=current_user.id,
        project_name=request.project_name,
    )
    return {"message": "Dispatch acknowledged. Aura is now executing the mission plan."}


@router.post("/{project_name}/stop", status_code=status.HTTP_200_OK)
async def stop_agent_mission(
    project_name: str, # Included for path consistency, but not strictly needed
    current_user: User = Depends(get_current_user)
):
    """
    Signals the running mission for the current user to stop gracefully.
    """
    user_id = str(current_user.id)
    logger.info(f"Received stop request for user {user_id}'s mission.")
    await mission_control.request_mission_stop(user_id)
    return {"message": f"Stop signal sent for user {user_id}'s mission."}


@router.get("/", response_model=List[str])
async def list_user_projects(
        aura_services: ServiceManager = Depends(get_aura_services)
):
    try:
        return aura_services.project_manager.list_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {e}")


@router.post("/{project_name}", status_code=status.HTTP_201_CREATED)
async def create_new_project(
        project_name: str,
        aura_services: ServiceManager = Depends(get_aura_services)
):
    try:
        project_path = aura_services.project_manager.new_project(project_name)
        return {"message": "Project created successfully.", "project_path": project_path}
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {e}")


@router.post("/{project_name}/load", status_code=status.HTTP_200_OK)
async def load_project_and_auto_index(
        project_name: str,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    project_manager: ProjectManager = aura_services.project_manager
    project_path_str = project_manager.load_project(project_name)
    if not project_path_str:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    project_path = Path(project_path_str)
    vcs: VectorContextService = aura_services.vector_context_service
    message = f"Project '{project_name}' loaded successfully."

    if vcs:
        # --- THE FIX ---
        vcs.load_for_project(project_path, current_user.id)
        # --- END FIX ---
        if vcs.collection and vcs.collection.count() == 0:
            message += " Initial project scan for AI context has been started in the background."
            background_tasks.add_task(
                run_initial_project_index,
                services=aura_services,
                user_id=current_user.id,
                project_name=project_name
            )
    try:
        file_tree = project_manager.get_file_tree()
        await websocket_manager.broadcast_to_user({
            "type": "file_tree_updated",
            "content": file_tree
        }, str(current_user.id))
    except Exception as e:
        logger.error(f"Error sending file tree for user {current_user.id}: {e}")

    return {"message": message}


@router.delete("/{project_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_project(
        project_name: str,
        aura_services: ServiceManager = Depends(get_aura_services)
):
    try:
        aura_services.project_manager.delete_project(project_name)
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
        aura_services: ServiceManager = Depends(get_aura_services)
):
    project_manager: ProjectManager = aura_services.project_manager
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")
    return project_manager.get_file_tree()


@router.get("/workspace/{project_name}/file")
async def get_project_file_content(
        project_name: str,
        path: str = Query(...),
        aura_services: ServiceManager = Depends(get_aura_services)
):
    project_manager: ProjectManager = aura_services.project_manager
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
    project_manager: ProjectManager = aura_services.project_manager
    project_path_str = project_manager.load_project(project_name)
    if not project_path_str:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found.")

    full_file_path_str = project_manager.write_file(request.path, request.content)
    if full_file_path_str is None:
        raise HTTPException(status_code=400, detail="Invalid file path or failed to write file.")

    background_tasks.add_task(
        run_reindex_task,
        services=aura_services,
        user_id=current_user.id,
        project_name=project_name,
        file_path_str=full_file_path_str,
        content=request.content
    )

    return None