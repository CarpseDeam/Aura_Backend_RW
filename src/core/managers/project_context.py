# core/managers/project_context.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class ProjectContext:
    """
    An immutable snapshot of the active project's environment details.
    """
    project_root: Path
    venv_python_path: Optional[Path] = None
    venv_pip_path: Optional[Path] = None