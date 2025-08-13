# foundry/actions/dependency_management_actions.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def add_dependency_to_requirements(path: str = "requirements.txt", dependency: str = "") -> str:
    """
    Safely adds a dependency to a requirements.txt file.

    It creates the file if it doesn't exist and ensures the dependency is not
    already listed before appending it. It checks for the package name to avoid
    duplicates even with different version specifiers.

    Args:
        path: The path to the requirements.txt file.
        dependency: The dependency to add (e.g., 'flask' or 'pytest==7.4.0').

    Returns:
        A string indicating the result of the operation.
    """
    if not dependency:
        return "Error: No dependency provided."

    logger.info(f"Attempting to add dependency '{dependency}' to '{path}'")
    req_file = Path(path)
    package_name = dependency.split('==')[0].split('>')[0].split('<')[0].strip()

    try:
        # Create the file and its directories if it doesn't exist
        req_file.parent.mkdir(parents=True, exist_ok=True)
        if not req_file.exists():
            req_file.touch()

        # Read existing dependencies
        with open(req_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        existing_packages = {line.split('==')[0].split('>')[0].split('<')[0].strip() for line in lines}

        if package_name in existing_packages:
            message = f"Dependency '{package_name}' already exists in '{path}'. No changes made."
            logger.warning(message)
            return message

        # Append the new dependency
        with open(req_file, 'a', encoding='utf-8') as f:
            if lines and not lines[-1].endswith('\n'):
                f.write('\n')
            f.write(f"{dependency}\n")

        success_message = f"Successfully added '{dependency}' to '{path}'."
        logger.info(success_message)
        return success_message

    except Exception as e:
        error_message = f"An unexpected error occurred while managing dependencies: {e}"
        logger.exception(error_message)
        return error_message