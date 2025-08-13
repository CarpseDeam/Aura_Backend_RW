# foundry/actions/interactive_actions.py
"""
Contains actions that require interaction with the user.
"""
import logging
from src.foundry.blueprints import UserInputRequest

logger = logging.getLogger(__name__)

def request_user_input(question: str) -> UserInputRequest:
    """
    Signals the system to pause and ask the user a question.

    This function does not execute logic itself, but returns a special
    request object that the ExecutorService will interpret to pause the
    execution flow and await user input.

    Args:
        question: The question to display to the user.

    Returns:
        A UserInputRequest object containing the question.
    """
    logger.info(f"Action triggered to ask user: '{question}'")
    return UserInputRequest(question=question)