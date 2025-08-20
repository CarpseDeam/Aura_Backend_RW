# src/services/tool_runner_service.py
import logging
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
import inspect
import asyncio

from src.core.websockets import websocket_manager
from src.event_bus import EventBus
from src.foundry import FoundryManager, BlueprintInvocation

if TYPE_CHECKING:
    from src.core.managers import ServiceManager

logger = logging.getLogger(__name__)


class ToolRunnerService:
    """
    Handles the safe execution of a single BlueprintInvocation.
    It resolves paths and injects context before calling the action function.
    """

    def __init__(
            self,
            event_bus: EventBus,
            service_manager: "ServiceManager"
    ):
        self.event_bus = event_bus
        self.service_manager = service_manager
        self.PATH_PARAM_KEYS = ['path', 'source_path', 'destination_path', 'requirements_path']
        self.FILESYSTEM_TOOLS = [
            'write_file', 'append_to_file', 'create_directory', 'create_package_init',
            'delete_directory', 'copy_file', 'move_file', 'delete_file',
            'add_dependency_to_requirements'
        ]
        logger.info("ToolRunnerService initialized.")

    def _get_service_map(self):
        """
        Dynamically creates the service map to ensure it always has the latest
        service instances, especially after a project change.
        It now fetches directly from the authoritative ServiceManager.
        """
        return {
            'project_manager': self.service_manager.project_manager,
            'mission_log_service': self.service_manager.mission_log_service,
            'vector_context_service': self.service_manager.vector_context_service,
            'development_team_service': self.service_manager.development_team_service,
            'llm_client': self.service_manager.llm_client,
            'event_bus': self.event_bus,
        }

    async def run_tool_by_dict(self, tool_call_dict: dict, user_id: str) -> Optional[Any]:
        """Convenience method to run a tool from a dictionary."""
        tool_name = tool_call_dict.get("tool_name")
        foundry_manager = self.service_manager.foundry_manager
        blueprint = foundry_manager.get_blueprint(tool_name)
        if not blueprint:
            error_msg = f"Error: Blueprint '{tool_name}' not found in Foundry."
            print(error_msg)
            return error_msg

        invocation = BlueprintInvocation(blueprint=blueprint, parameters=tool_call_dict.get('arguments', {}))
        return await self.run_tool(invocation, user_id)

    async def run_tool(self, invocation: BlueprintInvocation, user_id: str) -> Optional[Any]:
        """Executes a single blueprint invocation."""
        blueprint = invocation.blueprint
        action_id = blueprint.id
        foundry_manager = self.service_manager.foundry_manager

        action_function = foundry_manager.get_action(blueprint.action_function_name)
        if not action_function:
            error_msg = f"Error: Action function '{blueprint.action_function_name}' not found."
            print(error_msg)
            return error_msg

        execution_params = self._prepare_parameters(action_function, invocation.parameters)
        display_params = self._create_display_params(execution_params)

        print(f"▶️  Executing: {action_id} with params {display_params}")

        # --- NEW UX IMPROVEMENT ---
        # If we're about to write a file, notify the UI immediately so it can
        # open a tab and show a pending state.
        if action_id == 'write_file' and 'path' in execution_params:
            project_manager = self.service_manager.project_manager
            try:
                full_path = Path(execution_params['path'])
                relative_path = str(full_path.relative_to(project_manager.active_project_path))
                await websocket_manager.broadcast_to_user({
                    "type": "file_writing_pending",
                    "content": {"filePath": relative_path}
                }, user_id)
            except Exception as e:
                # Non-critical error, just log it.
                logger.warning(f"Could not send file_writing_pending message: {e}")

        await asyncio.sleep(0.1)

        result = None
        status = "FAILURE"
        try:
            if inspect.iscoroutinefunction(action_function):
                result = await action_function(**execution_params)
            else:
                result = action_function(**execution_params)

            if isinstance(result, str) and result.strip().lower().startswith("error"):
                status = "FAILURE"
            elif isinstance(result, dict) and result.get('status') in ["failure", "error"]:
                status = "FAILURE"
            else:
                status = "SUCCESS"

            project_manager = self.service_manager.project_manager
            if status == "SUCCESS" and action_id in self.FILESYSTEM_TOOLS:
                file_tree = project_manager.get_file_tree()
                await websocket_manager.broadcast_to_user({
                    "type": "file_tree_updated",
                    "content": file_tree
                }, user_id)

                if action_id == 'write_file' and 'path' in execution_params:
                    file_path_str = execution_params['path']
                    try:
                        content = Path(file_path_str).read_text(encoding='utf-8')
                        relative_path = str(Path(file_path_str).relative_to(project_manager.active_project_path))
                        await websocket_manager.broadcast_to_user({
                            "type": "file_content_updated",
                            "content": {
                                "filePath": relative_path,
                                "content": content
                            }
                        }, user_id)
                    except Exception as e:
                        logger.error(f"Could not read file content after write to send to UI: {e}")

            print(f"✅ Result from {action_id}: {result}")
            return result

        except Exception as e:
            logger.exception("An exception occurred while executing blueprint '%s'.", action_id)
            result = f"❌ Error executing Blueprint '{action_id}': {e}"
            print(result)
            return result
        finally:
            pass

    def _prepare_parameters(self, action_function: callable, action_params: dict) -> dict:
        execution_params = action_params.copy()
        project_manager = self.service_manager.project_manager
        base_path: Optional[Path] = project_manager.active_project_path
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
                execution_params['project_context'] = project_manager.active_project_context

        return execution_params

    def _create_display_params(self, execution_params: dict) -> dict:
        display_params = {}
        service_keys = list(self._get_service_map().keys()) + ['project_context']
        project_manager = self.service_manager.project_manager

        for key, value in execution_params.items():
            if key not in service_keys:
                display_params[key] = value

        base_path = project_manager.active_project_path
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