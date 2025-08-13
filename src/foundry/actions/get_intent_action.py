# foundry/actions/get_intent_action.py
import logging
from pathlib import Path
from src.core.managers import ProjectContext

logger = logging.getLogger(__name__)


def get_intent(project_context: ProjectContext) -> str:
    """
    Reads the content of the 'intent.md' file from the project root and returns it as a string.
    """
    if not project_context:
        return "Error: Project context is not available. Cannot locate intent.md."

    try:
        intent_path = project_context.project_root / 'intent.md'
        logger.info(f"Attempting to read intent file from: {intent_path}")
        if intent_path.exists():
            return intent_path.read_text(encoding='utf-8')
        else:
            return "The 'intent.md' file was not found in the project root."
    except Exception as e:
        logger.error(f"An error occurred while reading the intent file: {e}", exc_info=True)
        return f"An error occurred while reading the intent file: {e}"