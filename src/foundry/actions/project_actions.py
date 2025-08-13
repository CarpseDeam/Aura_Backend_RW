# foundry/actions/project_actions.py
"""
Contains actions related to project management.
"""
import logging
from src.core.managers.project_manager import ProjectManager

logger = logging.getLogger(__name__)


def create_project(project_manager: ProjectManager, project_name: str) -> str:
    """
    Action to create a new project directory and set it as active.

    Args:
        project_manager: The ProjectManager service instance.
        project_name: The name of the project to create.

    Returns:
        A string indicating the result of the operation.
    """
    logger.info(f"Executing create_project action with name: {project_name}")
    path = project_manager.new_project(project_name)
    if path:
        return f"Successfully created new project at: {path}"
    else:
        return "Failed to create new project."