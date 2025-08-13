# foundry/actions/pip_install_action.py
import logging
import subprocess
from pathlib import Path

from src.core.managers import ProjectContext

logger = logging.getLogger(__name__)


def pip_install(project_context: ProjectContext, requirements_path: str = "requirements.txt") -> str:
    """
    Installs dependencies from a requirements file using the project's virtual environment.
    """
    if not project_context or not project_context.project_root:
        return "Error: Cannot run pip install. No active project context."

    # Determine pip command, preferring direct executable but falling back to module invocation
    if project_context.venv_pip_path and project_context.venv_pip_path.exists():
        pip_command_base = [str(project_context.venv_pip_path)]
    elif project_context.venv_python_path and project_context.venv_python_path.exists():
        logger.warning("Could not find pip executable, attempting to run via 'python -m pip'")
        pip_command_base = [str(project_context.venv_python_path), "-m", "pip"]
    else:
        return "Error: No virtual environment Python or pip executable found. Cannot install dependencies."

    working_dir = project_context.project_root
    req_file = Path(requirements_path)

    if not req_file.exists():
        return f"Error: requirements file not found at '{req_file}'. Please create it first."

    install_command = pip_command_base + ["install", "-r", str(req_file)]

    logger.info(f"Executing command: '{' '.join(install_command)}' in '{working_dir}'")
    try:
        result = subprocess.run(
            install_command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(working_dir),
            shell=False
        )
        return f"Successfully installed dependencies from {requirements_path}.\n---STDOUT---\n{result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Error installing dependencies.\nReturn Code: {e.returncode}\n---STDERR---\n{e.stderr}"
    except FileNotFoundError:
        return f"Error: Command '{pip_command_base[0]}' not found. The virtual environment might be corrupted."
    except Exception as e:
        return f"An unexpected error occurred during pip install: {e}"