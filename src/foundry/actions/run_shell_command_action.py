# foundry/actions/run_shell_command_action.py
import logging
import subprocess
import shlex
import os
from src.core.managers import ProjectContext

logger = logging.getLogger(__name__)


def run_shell_command(project_context: ProjectContext, command: str) -> str:
    """
    Executes a shell command within the project's context, intelligently using
    the project's virtual environment if 'python' or 'pip' are called.
    """
    if not project_context:
        return "Error: Cannot run shell command. No active project context."

    working_dir = str(project_context.project_root)
    logger.info(f"Executing shell command: '{command}' in directory '{working_dir}'")

    try:
        command_parts = shlex.split(command, posix=os.name != 'nt')
        if not command_parts:
            return "Error: Empty command provided."

        # --- Venv-Aware Execution Logic ---
        # Intercept python and pip calls to use the venv executables if they exist.
        executable_name = command_parts[0].lower()

        # Be very specific to avoid accidentally matching other scripts.
        if (executable_name == 'python' or executable_name == 'python.exe') and project_context.venv_python_path:
            original_executable = command_parts[0]
            command_parts[0] = str(project_context.venv_python_path)
            logger.info(f"Intercepted '{original_executable}'. Using venv executable: {command_parts[0]}")
        elif (executable_name == 'pip' or executable_name == 'pip.exe') and project_context.venv_pip_path:
            original_executable = command_parts[0]
            command_parts[0] = str(project_context.venv_pip_path)
            logger.info(f"Intercepted '{original_executable}'. Using venv executable: {command_parts[0]}")

        result = subprocess.run(
            command_parts,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            cwd=working_dir,
            shell=False
        )
        output = f"Command executed successfully.\n--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}"
        logger.info(f"Command '{command}' succeeded.")
        return output
    except subprocess.CalledProcessError as e:
        error_output = (
            f"Error executing command: '{command}'\n"
            f"Return Code: {e.returncode}\n"
            f"--- STDOUT ---\n{e.stdout}\n"
            f"--- STDERR ---\n{e.stderr}"
        )
        logger.error(error_output)
        return error_output
    except FileNotFoundError:
        error_output = f"An unexpected error occurred: Command not found '{command_parts[0]}'. Make sure it's a valid command and in the system's PATH."
        logger.exception(error_output)
        return error_output
    except Exception as e:
        error_output = f"An unexpected error occurred while trying to run command '{command}': {e}"
        logger.exception(error_output)
        return error_output