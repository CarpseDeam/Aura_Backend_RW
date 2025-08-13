# foundry/actions/code_quality_actions.py
"""
Contains actions related to code quality, such as linting.
"""
import logging
import pycodestyle
import io
from contextlib import redirect_stdout

from src.core.managers import ProjectContext

logger = logging.getLogger(__name__)


def lint_file(path: str) -> str:
    """
    Lints a Python file using pycodestyle (PEP8) and returns the results.
    """
    logger.info(f"Linting file: {path}")
    try:
        style_guide = pycodestyle.StyleGuide(quiet=False)
        string_io = io.StringIO()
        with redirect_stdout(string_io):
            result = style_guide.check_files([path])
        output = string_io.getvalue()

        if result.total_errors == 0:
            return f"Linting complete for '{path}': No issues found! Excellent code quality."
        else:
            return f"Linting found {result.total_errors} issue(s) in '{path}':\n{output}"
    except FileNotFoundError:
        return f"Error: File not found at '{path}'."
    except Exception as e:
        return f"An unexpected error occurred during linting: {e}"