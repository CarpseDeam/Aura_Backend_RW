# src/core/managers/__init__.py
"""
Exports key manager classes for clean, direct importing from the 'managers' package.
This simplifies access to essential components of Aura's core architecture.
"""
from .event_coordinator import EventCoordinator
from .git_manager import GitManager
from .project_context import ProjectContext
from .project_manager import ProjectManager
from .service_manager import ServiceManager
from .task_manager import TaskManager
from .venv_manager import VenvManager
from .window_manager import WindowManager
from .workflow_manager import WorkflowManager

__all__ = [
    'EventCoordinator',
    'GitManager',
    'ProjectContext',
    'ProjectManager',
    'ServiceManager',
    'TaskManager',
    'VenvManager',
    'WindowManager',
    'WorkflowManager',
]