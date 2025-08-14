# src/core/llm_client.py
from typing import Dict, Tuple


class LLMClient:
    """
    A lightweight class responsible for managing model role assignments for a user.
    This is a slimmed-down, web-native version. It does not make API calls itself.
    """

    def __init__(self):
        self.role_assignments: Dict[str, str] = {}
        self.role_temperatures: Dict[str, float] = {}
        print("[LLMClient] Web-native client initialized. Role assignments will be provided by the database.")

    def set_assignments(self, assignments: Dict[str, str]):
        """Sets the current assignments, loaded from the database for a specific user request."""
        self.role_assignments = assignments

    def set_temperatures(self, temperatures: Dict[str, float]):
        """Sets the current temperature overrides."""
        self.role_temperatures = temperatures

    def get_role_temperature(self, role: str) -> float:
        """Gets the temperature for a role, with a default."""
        return self.role_temperatures.get(role, 0.7)

    def get_model_for_role(self, role: str) -> Tuple[str | None, str | None]:
        """
        Gets the model identifier for a given role with a robust fallback.
        e.g., ("google", "gemini-2.5-pro")
        """
        key = self.role_assignments.get(role)

        # If the specific role is not found, try a sensible fallback.
        if not key:
            fallback_order = ["coder", "planner", "chat"]
            for fallback_role in fallback_order:
                key = self.role_assignments.get(fallback_role)
                if key:
                    break

            # If still no key, just grab the first one available.
            if not key and self.role_assignments:
                key = next(iter(self.role_assignments.values()), None)

        if not key or "/" not in key:
            return None, None

        provider, model_name = key.split('/', 1)
        return provider, model_name