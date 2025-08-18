# src/api/missions.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pathlib import Path

from src.dependencies import get_aura_services
from src.core.managers import ServiceManager, ProjectManager
from src.services import MissionLogService, VectorContextService
from src.db.models import User
from src.api.auth import get_current_user
from src.schemas import mission as schemas

router = APIRouter(
    prefix="/missions",
    tags=["Mission Control"]
)

# Helper dependency to get the mission log service and load the project
async def get_project_mission_log(
    project_name: str,
    aura_services: ServiceManager = Depends(get_aura_services)
) -> MissionLogService:
    """
    A dependency that loads the specified project and returns the
    mission log service ready to operate on it.
    """
    project_manager: ProjectManager = aura_services.get_project_manager()
    project_path = project_manager.load_project(project_name)
    if not project_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_name}' not found for this user."
        )

    vcs: VectorContextService = aura_services.vector_context_service
    if vcs:
        vcs.load_for_project(Path(project_path))

    mission_log_service: MissionLogService = aura_services.mission_log_service
    # Ensure the log for the just-loaded project is active in the service
    mission_log_service.load_log_for_active_project()
    return mission_log_service


@router.post("/{project_name}/tasks", status_code=status.HTTP_201_CREATED, response_model=schemas.Task)
async def add_mission_task(
    project_name: str,
    request: schemas.TaskCreateRequest,
    mission_log: MissionLogService = Depends(get_project_mission_log),
    current_user: User = Depends(get_current_user)
):
    """Adds a new task to a project's mission log."""
    try:
        new_task = await mission_log.add_task(user_id=str(current_user.id), description=request.description)
        return new_task
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{project_name}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_mission_task(
    project_name: str,
    task_id: int,
    request: schemas.TaskUpdateRequest,
    mission_log: MissionLogService = Depends(get_project_mission_log),
    current_user: User = Depends(get_current_user)
):
    """Updates the description of an existing task."""
    try:
        success = await mission_log.update_task(
            user_id=str(current_user.id),
            task_id=task_id,
            description=request.description
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with ID {task_id} not found.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{project_name}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission_task(
    project_name: str,
    task_id: int,
    mission_log: MissionLogService = Depends(get_project_mission_log),
    current_user: User = Depends(get_current_user)
):
    """Deletes a task from the mission log."""
    success = await mission_log.delete_task(user_id=str(current_user.id), task_id=task_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with ID {task_id} not found.")


@router.post("/{project_name}/tasks/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_mission_tasks(
    project_name: str,
    request: schemas.TasksReorderRequest,
    mission_log: MissionLogService = Depends(get_project_mission_log),
    current_user: User = Depends(get_current_user)
):
    """Reorders all tasks based on a provided list of task IDs."""
    success = await mission_log.reorder_tasks(
        user_id=str(current_user.id),
        ordered_task_ids=request.ordered_task_ids
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reorder tasks. The provided list of IDs may be invalid or incomplete."
        )