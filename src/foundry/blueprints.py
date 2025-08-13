# foundry/blueprints.py

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Blueprint:
    """
    Represents a self-contained, executable tool that the AVM can use.
    """
    id: str
    description: str
    parameters: Dict[str, Any]
    action_function_name: str
    template: str = ""

@dataclass
class BlueprintInvocation:
    """Represents a specific invocation of a tool based on a Blueprint."""
    blueprint: Blueprint
    parameters: Dict[str, Any]

@dataclass
class RawCodeInstruction:
    """
    Represents a direct, raw code instruction to be executed or displayed.
    """
    code: str
    language: str = "python"


@dataclass
class UserInputRequest:
    """A special object returned by an action to signal a pause for user input."""
    question: str