# src/foundry/foundry_manager.py
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.foundry.blueprints import Blueprint

logger = logging.getLogger(__name__)


class FoundryManager:
    """
    Manages Blueprints and Actions by dynamically discovering them from the filesystem.
    """

    def __init__(self) -> None:
        self._blueprints: Dict[str, Blueprint] = {}
        self._actions: Dict[str, Callable[..., Any]] = {}

        self.rescan_and_load()

    def handle_tools_modified(self, event) -> None:
        """Event handler to rescan tools when notified."""
        logger.info("ToolsModified event received. Rescanning blueprints and actions...")
        self.rescan_and_load()

    def rescan_and_load(self) -> None:
        """
        Clears and re-loads all blueprints and actions from the filesystem.
        This makes the Foundry dynamic and responsive to new tools being created.
        """
        # Clear existing dictionaries
        self._blueprints.clear()
        self._actions.clear()
        logger.info("Cleared existing blueprints and actions for rescan.")

        # Reload everything
        self._discover_and_load_actions()
        self._discover_and_load_blueprints()

        logger.info(
            f"FoundryManager re-initialized with {len(self._blueprints)} blueprints and {len(self._actions)} actions.")

    def _add_blueprint(self, blueprint: Blueprint) -> None:
        if blueprint.action_function_name not in self._actions:
            logger.error(
                f"Blueprint '{blueprint.id}' references an action function "
                f"'{blueprint.action_function_name}' that was not found. "
                "This blueprint will be disabled."
            )
            return

        if blueprint.id in self._blueprints:
            logger.warning("Blueprint with id '%s' is being overwritten.", blueprint.id)

        self._blueprints[blueprint.id] = blueprint
        logger.debug("Registered blueprint: %s", blueprint.id)

    def _discover_and_load_blueprints(self) -> None:
        try:
            blueprints_dir = Path(__file__).parent.parent / "blueprints"
            package_name = "src.blueprints"
            for file_path in blueprints_dir.glob("*.py"):
                if file_path.name.startswith("__"): continue
                module_name = f"{package_name}.{file_path.stem}"
                try:
                    # The key to reloading is to invalidate Python's cache
                    if module_name in inspect.sys.modules:
                         importlib.reload(inspect.sys.modules[module_name])

                    module = importlib.import_module(module_name)
                    if hasattr(module, "blueprint") and isinstance(module.blueprint, Blueprint):
                        self._add_blueprint(module.blueprint)
                        logger.info("Loaded blueprint '%s' from %s.", module.blueprint.id, file_path.name)
                    else:
                        logger.warning("File %s does not contain a valid 'blueprint' instance.", file_path.name)
                except Exception as e:
                    logger.error(f"Failed to load blueprint from %s: %s", file_path.name, e, exc_info=True)
        except Exception as e:
            logger.critical("A critical error occurred during blueprint discovery: %s", e, exc_info=True)

    def _discover_and_load_actions(self) -> None:
        try:
            actions_dir = Path(__file__).parent / "actions"
            package_name = "src.foundry.actions"
            if not actions_dir.is_dir() or not (actions_dir / "__init__.py").exists():
                logger.error(
                    f"Action discovery failed: The directory 'foundry/actions/' or its '__init__.py' file is missing.")
                return
            for file_path in actions_dir.glob("*.py"):
                if file_path.name.startswith("__"): continue
                module_name = f"{package_name}.{file_path.stem}"
                try:
                    # The key to reloading is to invalidate Python's cache
                    if module_name in inspect.sys.modules:
                        importlib.reload(inspect.sys.modules[module_name])

                    module = importlib.import_module(module_name)
                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        # Only register the function if it was DEFINED in this module
                        if func.__module__ == module_name:
                            if name in self._actions:
                                logger.warning(f"Action function '{name}' is being overwritten by module '{module_name}'.")
                            self._actions[name] = func
                            logger.debug(f"Registered action function: {name} from {file_path.name}")
                except ImportError as e:
                    logger.error(f"Failed to import action module {module_name}: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Failed to load actions from {file_path.name}: {e}", exc_info=True)
        except Exception as e:
            logger.critical(f"A critical error occurred during action discovery: {e}", exc_info=True)

    def get_blueprint(self, name: str) -> Optional[Blueprint]:
        return self._blueprints.get(name)

    def get_action(self, name: str) -> Optional[Callable[..., Any]]:
        return self._actions.get(name)

    def get_llm_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Gets the list of tool definitions in a generic format, ready to be
        transformed by a provider-specific method if necessary.
        """
        definitions: List[Dict[str, Any]] = []
        for bp in self._blueprints.values():
            tool_def = {
                "name": bp.id,
                "description": bp.description,
                "parameters": bp.parameters
            }
            definitions.append(tool_def)
        return definitions