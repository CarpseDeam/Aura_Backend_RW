# src/foundry/__init__.py
"""
This file makes the 'foundry' directory a Python package and exposes key
classes like FoundryManager and Blueprint for easy access from other parts
of the application.
"""
from .foundry_manager import FoundryManager
from .blueprints import Blueprint, BlueprintInvocation, UserInputRequest

__all__ = [
    "FoundryManager",
    "Blueprint",
    "BlueprintInvocation",
    "UserInputRequest",
]