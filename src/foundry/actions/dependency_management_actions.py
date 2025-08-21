# foundry/actions/dependency_management_actions.py
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def add_dependency_to_requirements(path: str = "requirements.txt", dependencies: List[str] = None) -> str:
    """
    Safely adds one or more dependencies to a requirements.txt file.
    """
    if not dependencies:
        return "Error: No dependencies provided."

    logger.info(f"Attempting to add dependencies '{', '.join(dependencies)}' to '{path}'")
    req_file = Path(path)
    added_deps = []
    existing_deps = []

    try:
        req_file.parent.mkdir(parents=True, exist_ok=True)
        if not req_file.exists():
            req_file.touch()

        with open(req_file, 'r+', encoding='utf-8') as f:
            lines = f.readlines()
            existing_packages = {line.split('==')[0].split('>')[0].split('<')[0].strip().lower() for line in lines}

            for dep in dependencies:
                package_name = dep.split('==')[0].split('>')[0].split('<')[0].strip().lower()
                if package_name not in existing_packages:
                    if lines and not lines[-1].endswith('\n'):
                        f.write('\n')
                    f.write(f"{dep}\n")
                    added_deps.append(dep)
                    existing_packages.add(package_name) # Add to set to handle duplicates in the input list
                else:
                    existing_deps.append(dep)

        message_parts = []
        if added_deps:
            message_parts.append(f"Successfully added: {', '.join(added_deps)}.")
        if existing_deps:
            message_parts.append(f"Already existed: {', '.join(existing_deps)}.")

        return " ".join(message_parts) if message_parts else "No changes made to requirements.txt."

    except Exception as e:
        error_message = f"An unexpected error occurred while managing dependencies: {e}"
        logger.exception(error_message)
        return error_message