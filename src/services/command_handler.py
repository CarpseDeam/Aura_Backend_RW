# src/services/command_handler.py
import logging
import re
from typing import Callable, Dict, TYPE_CHECKING
from src.foundry import FoundryManager
from .view_formatter import format_as_box
from src.events import DisplayFileInEditor, DirectToolInvocationRequest, UserPromptEntered, UserCommandEntered
from src.event_bus import EventBus

if TYPE_CHECKING:
    from src.core.managers import ProjectManager

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Handles direct, CLI-style slash commands from the user. It provides a fast,
    deterministic path for actions that don't require LLM reasoning.
    """

    def __init__(self, foundry_manager: FoundryManager, event_bus: EventBus,
                 project_manager: "ProjectManager", display_callback, output_log_text_fetcher: Callable[[], str]):
        self.foundry = foundry_manager
        self.event_bus = event_bus
        self.project_manager = project_manager
        self.display = display_callback
        self.output_log_text_fetcher = output_log_text_fetcher
        self.last_aura_response = ""

        self.commands = {
            "build": "Sends the last prompt from Plan mode to Build mode.",
            "help": "Shows the detailed help message.",
            "index": "Re-indexes the project for the AI.",
            "list_files": "Lists files in the active project.",
            "read": "Reads a file into the Code Viewer.",
            "lint": "Lints a Python file."
        }

        logger.info("CommandHandler initialized and ready.")

    def get_available_commands(self) -> Dict[str, str]:
        """Returns the dictionary of available commands for the autocomplete popup."""
        return self.commands

    def _update_last_aura_response(self):
        """Scan the log to find the last message from Aura."""
        full_text = self.output_log_text_fetcher()
        matches = list(re.finditer(r'\[ Aura \]\n(.*?)\s*$', full_text, re.S | re.M))
        if matches:
            self.last_aura_response = matches[-1].group(1).strip()
            logger.info(f"Captured last Aura response for /build command.")
        else:
            self.last_aura_response = ""
            logger.warning("Could not find a previous 'Aura' response to use for /build.")

    def handle(self, event: UserCommandEntered):
        self._update_last_aura_response()

        command = event.command.lower()
        args = event.args
        logger.info(f"Handling command '/{command}' with args: {args}")

        try:
            if command == "build":
                self._handle_build()
            elif command == "list_files":
                self._handle_list_files(args)
            elif command == "read":
                self._handle_read_file(args)
            elif command == "lint":
                self._handle_lint(args)
            elif command == "index":
                self._handle_index()
            elif command == "help":
                self._handle_help()
            else:
                error_text = f"Unknown command: /{command}\nType /help to see a list of available commands."
                self.display(format_as_box(f"Error: Unknown Command", error_text), "avm_error")
        except Exception as e:
            error_message = f"An unexpected error occurred while executing '/{command}': {e}"
            logger.error(error_message, exc_info=True)
            self.display(format_as_box(f"Error: {command}", error_message), "avm_error")

    def _handle_build(self):
        if not self.last_aura_response:
            self.display(format_as_box("Error", "No previous response from Aura to build from."), "avm_error")
            return

        self.display(f"▶️ Sending last prompt to Build Mode...", "system_message")
        event = UserPromptEntered(
            prompt_text=self.last_aura_response,
            conversation_history=[]
        )
        self.event_bus.emit("user_request_submitted", event)

    def _handle_list_files(self, args: list):
        list_files_action = self.foundry.get_action("list_files")
        relative_path = args[0] if args else "."
        if not self.project_manager.active_project_path:
            self.display(format_as_box("Error", "No active project."), "avm_error")
            return
        resolved_path = self.project_manager.active_project_path / relative_path
        result = list_files_action(path=str(resolved_path))
        display_path = self.project_manager.active_project_name or "Current Directory"
        if relative_path != ".":
            display_path = f"{display_path}/{relative_path}"
        formatted_output = format_as_box(f"Directory Listing: {display_path}", result)
        self.display(formatted_output, "avm_output")

    def _handle_read_file(self, args: list):
        if not args:
            self.display(format_as_box("Usage Error", "Please provide a file path.\nUsage: /read <path/to/file>"),
                         "avm_error")
            return
        read_file_action = self.foundry.get_action("read_file")
        relative_path = args[0]
        if not self.project_manager.active_project_path:
            self.display(format_as_box("Error", "No active project."), "avm_error")
            return
        resolved_path = self.project_manager.active_project_path / relative_path
        content = read_file_action(path=str(resolved_path))
        if content.strip().startswith("Error:"):
            self.display(format_as_box(f"Error reading file", content), "avm_error")
            return
        self.event_bus.emit("display_file_in_editor", DisplayFileInEditor(file_path=str(resolved_path), file_content=content))
        self.display(f"Opened `{relative_path}` in Code Viewer.", "system_message")

    def _handle_lint(self, args: list):
        if not args:
            self.display(format_as_box("Usage Error", "Please provide a file path.\nUsage: /lint <path/to/file>"),
                         "avm_error")
            return
        lint_action = self.foundry.get_action("lint_file")
        relative_path = args[0]
        if not self.project_manager.active_project_path:
            self.display(format_as_box("Error", "No active project."), "avm_error")
            return
        resolved_path = self.project_manager.active_project_path / relative_path
        result = lint_action(path=str(resolved_path))
        formatted_output = format_as_box(f"Lint Report: {relative_path}", result)
        self.display(formatted_output, "avm_output")

    def _handle_index(self):
        if not self.project_manager.active_project_path:
            self.display(format_as_box("Error", "No active project. Please create or load a project first."),
                         "avm_error")
            return
        self.display("Starting project re-indexing...", "system_message")
        self.event_bus.emit('direct_tool_invocation_request', DirectToolInvocationRequest(tool_id='index_project_context', params={
            'path': str(self.project_manager.active_project_path)}))

    def _handle_help(self):
        help_text = "Aura Direct Commands:\n\n"
        for cmd, desc in self.commands.items():
            help_text += f"/{cmd.ljust(18)} - {desc}\n"
        self.display(format_as_box("Aura Help", help_text), "avm_output")