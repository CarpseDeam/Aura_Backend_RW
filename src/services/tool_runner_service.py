# src/services/tool_runner_service.py
import logging
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
import inspect
import asyncio
import copy

from src.event_bus import EventBus
from src.foundry import FoundryManager, BlueprintInvocation
from .mission_log_service import MissionLogService
from .vector_context_service import VectorContextService
from src.events import ToolCallInitiated, ToolCallCompleted, RefreshFileTree

if TYPE_CHECKING:
    from src.core.managers import ProjectManager, ProjectContext
    from src.core.llm_client import LLMClient
    from .development_team_service import DevelopmentTeamService

logger = logging.getLogger(__name__)


class ToolRunnerService:
    """
    Handles the safe execution of a single BlueprintInvocation.
    It resolves paths and injects context before calling the action function.
    """

    def __init__(
            self,
            event_bus: EventBus,
            foundry_manager: FoundryManager,
            project_manager: "ProjectManager",
            mission_log_service: MissionLogService,
            vector_context_service: Optional[VectorContextService] = None,
            development_team_service: Optional["DevelopmentTeamService"] = None,
            llm_client: Optional["LLMClient"] = None
    ):
        self.event_bus = event_bus
        self.foundry_manager = foundry_manager
        self.project_manager = project_manager
        self.mission_log_service = mission_log_service
        self.vector_context_service = vector_context_service
        self.development_team_service = development_team_service
        self.llm_client = llm_client

        self.PATH_PARAM_KEYS = ['path', 'source_path', 'destination_path', 'requirements_path']
        logger.info("ToolRunnerService initialized.")

    def _get_service_map(self):
        """
        Dynamically creates the service map to ensure it always has the latest
        service instances, especially after a project change.
        """
        return {
            'project_manager': self.project_manager,
            'mission_log_service': self.mission_log_service,
            'vector_context_service': self.vector_context_service,
            'development_team_service': self.development_team_service,
            'llm_client': self.llm_client,
            'event_bus': self.event_bus,
        }

    async def run_tool_by_dict(self, tool_call_dict: dict) -> Optional[Any]:
        """Convenience method to run a tool from a dictionary."""
        tool_name = tool_call_dict.get("tool_name")
        blueprint = self.foundry_manager.get_blueprint(tool_name)
        if not blueprint:
            error_msg = f"Error: Blueprint '{tool_name}' not found in Foundry."
            print(error_msg)
            return error_msg

        invocation = BlueprintInvocation(blueprint=blueprint, parameters=tool_call_dict.get('arguments', {}))
        return await self.run_tool(invocation)

    async def run_tool(self, invocation: BlueprintInvocation) -> Optional[Any]:
        """Executes a single blueprint invocation."""
        blueprint = invocation.blueprint
        action_id = blueprint.id

        action_function = self.foundry_manager.get_action(blueprint.action_function_name)
        if not action_function:
            error_msg = f"Error: Action function '{blueprint.action_function_name}' not found."
            print(error_msg)
            return error_msg

        execution_params = self._prepare_parameters(action_function, invocation.parameters)
        display_params = self._create_display_params(execution_params)

        print(f"▶️  Executing: {action_id} with params {display_params}")

        widget_id = id(invocation)
        self.event_bus.emit(
            "tool_call_initiated",
            ToolCallInitiated(widget_id, action_id, display_params)
        )
        await asyncio.sleep(0.1)

        result = None
        status = "FAILURE"
        try:
            if inspect.iscoroutinefunction(action_function):
                result = await action_function(**execution_params)
            else:
                result = action_function(**execution_params)

            # --- *** THE FIX IS HERE: INTELLIGENT STATUS CHECKING *** ---
            if isinstance(result, str) and result.strip().lower().startswith("error"):
                status = "FAILURE"
            elif isinstance(result, dict) and result.get('status') in ["failure", "error"]:
                status = "FAILURE"
            else:
                status = "SUCCESS"
            # --- END OF FIX ---

            if status == "SUCCESS":
                self.event_bus.emit("refresh_file_tree", RefreshFileTree())

            print(f"✅ Result from {action_id}: {result}")
            return result

        except Exception as e:
            logger.exception("An exception occurred while executing blueprint '%s'.", action_id)
            result = f"❌ Error executing Blueprint '{action_id}': {e}"
            print(result)
            return result
        finally:
            self.event_bus.emit(
                "tool_call_completed",
                ToolCallCompleted(widget_id, status, str(result))
            )

    def _prepare_parameters(self, action_function: callable, action_params: dict) -> dict:
        """
        Prepares parameters for EXECUTION.
        It resolves all file paths to ABSOLUTE paths to ensure sandbox safety.
        It injects necessary services.
        """
        execution_params = action_params.copy()
        base_path: Optional[Path] = self.project_manager.active_project_path
        sig = inspect.signature(action_function)
        service_map = self._get_service_map()

        if base_path:
            for key in self.PATH_PARAM_KEYS:
                if key in sig.parameters and key in execution_params:
                    relative_path_str = execution_params[key]
                    if isinstance(relative_path_str, str) and relative_path_str:
                        path_obj = Path(relative_path_str)
                        if not path_obj.is_absolute():
                            resolved_path = (base_path / path_obj).resolve()
                            execution_params[key] = str(resolved_path)

        for param_name in sig.parameters:
            if param_name in service_map:
                if service_map[param_name] is not None:
                    execution_params[param_name] = service_map[param_name]
            elif param_name == 'project_context':
                execution_params['project_context'] = self.project_manager.active_project_context

        return execution_params

    def _create_display_params(self, execution_params: dict) -> dict:
        """
        Creates a copy of parameters for display purposes, making paths relative.
        This version avoids deepcopying un-copyable service objects.
        """
        display_params = {}
        service_keys = list(self._get_service_map().keys()) + ['project_context']

        for key, value in execution_params.items():
            if key not in service_keys:
                display_params[key] = value

        base_path = self.project_manager.active_project_path
        if base_path:
            for key in self.PATH_PARAM_KEYS:
                if key in display_params and isinstance(display_params[key], str):
                    try:
                        abs_path = Path(display_params[key])
                        if abs_path.is_absolute():
                            display_params[key] = str(abs_path.relative_to(base_path))
                    except ValueError:
                        pass
        return display_params