# src/foundry/actions/run_tests_action.py
import logging
import subprocess
from src.core.managers import ProjectContext

logger = logging.getLogger(__name__)


def run_tests(project_context: ProjectContext) -> str:
    """
    Executes the project's test suite using pytest within the project's
    virtual environment.

    Args:
        project_context: The context of the active project, providing the
                         path to the venv Python executable.

    Returns:
        A string summarizing the test results or detailing the failure.
    """
    if not project_context or not project_context.project_root:
        return "Error: Cannot run tests. No active project context."

    if not project_context.venv_python_path or not project_context.venv_python_path.exists():
        return "Error: The project's virtual environment is not set up. Cannot find the Python executable to run pytest."

    working_dir = str(project_context.project_root)
    # Use the venv's python to run pytest as a module. This is the most reliable way.
    command = [
        str(project_context.venv_python_path),
        "-m",
        "pytest"
    ]

    # This is the corrected line.
    command_str = " ".join(command)
    logger.info(f"Executing test command: '{command_str}' in '{working_dir}'")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=working_dir,
            shell=False  # Security best practice
        )

        # Pytest exit codes:
        # 0: All tests passed
        # 1: Tests were collected and run but some failed
        # 2: Test execution was interrupted by the user
        # 3: Internal error occurred in pytest
        # 4: Pytest command line usage error
        # 5: No tests were collected

        if result.returncode == 0:
            success_message = f"All tests passed successfully!\n\n--- PYTEST OUTPUT ---\n{result.stdout}"
            logger.info(success_message)
            return success_message
        elif result.returncode == 5:
            no_tests_message = f"Pytest ran, but no tests were found to execute.\n\n--- PYTEST OUTPUT ---\n{result.stdout}"
            logger.warning(no_tests_message)
            return no_tests_message
        else:
            # Any other non-zero exit code is a failure.
            failure_message = (
                f"Error: One or more tests failed.\n\n"
                f"--- PYTEST STDOUT ---\n{result.stdout}\n\n"
                f"--- PYTEST STDERR ---\n{result.stderr}"
            )
            logger.error(failure_message)
            return failure_message

    except FileNotFoundError:
        error_msg = f"Error: Command '{command[0]}' not found. The project's virtual environment might be corrupted."
        logger.exception(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred while running tests: {e}"
        logger.exception(error_msg)
        return error_msg