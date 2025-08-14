import os
import json
import base64
from typing import Dict, Optional, Any, List
import aiohttp
from pathlib import Path


class LLMClient:
    """
    A lightweight client that communicates with the local LLM and RAG server processes.
    It does NOT load any heavy AI libraries itself.
    """

    def __init__(self, project_root: Path, llm_server_url="http://127.0.0.1:8002"):
        self.llm_server_url = llm_server_url
        self.project_root = project_root
        self.config_dir = project_root / "config"
        self.config_dir.mkdir(exist_ok=True, parents=True)
        self.assignments_file = self.config_dir / "role_assignments.json"
        self.default_assignments_file = self.config_dir / "default_role_assignments.json"
        self.role_assignments = {}
        self.role_temperatures = {}
        # In the new web backend, we don't load from local JSON files.
        # The assignments will be loaded from the database per request.
        # self.load_assignments()
        print(f"[LLMClient] Client initialized. Role assignments will be provided by the database.")

    def load_assignments(self):
        # This method is for the old desktop app and is no longer needed.
        # We'll keep it here for now to avoid breaking other parts of the old code.
        pass

    def save_assignments(self):
        # This is also a desktop-app-only method.
        pass

    async def get_available_models(self) -> dict:
        """Fetches the list of available models from the LLM server."""
        # This is also a legacy method. The new source of truth is the backend API.
        return {}

    def get_role_assignments(self) -> dict:
        return self.role_assignments.copy()

    def set_role_assignments(self, assignments: dict):
        self.role_assignments.update(assignments)

    def get_role_temperatures(self) -> dict:
        return self.role_temperatures.copy()

    def set_role_temperatures(self, temperatures: dict):
        self.role_temperatures.update(temperatures)

    def get_role_temperature(self, role: str) -> float:
        # A simple default temperature for now.
        return self.role_temperatures.get(role, 0.7)

    def get_model_for_role(self, role: str) -> tuple[str | None, str | None]:
        """
        Gets the model identifier for a given role with a robust fallback.
        """
        # First, try to get the specific role requested.
        key = self.role_assignments.get(role)

        # If the specific role is not found, try to find a sensible fallback.
        if not key:
            # Fallback priority: coder -> planner -> chat -> first available
            fallback_order = ["coder", "planner", "chat"]
            for fallback_role in fallback_order:
                key = self.role_assignments.get(fallback_role)
                if key:
                    break

            # If still no key, just grab the first one in the dictionary.
            if not key and self.role_assignments:
                key = next(iter(self.role_assignments.values()))

        if not key or "/" not in key:
            return None, None

        provider, model_name = key.split('/', 1)
        return provider, model_name

    async def stream_chat(self, provider: str, model: str, prompt: str, role: str = None,
                          image_bytes: Optional[bytes] = None, image_media_type: str = "image/png",
                          history: Optional[List[Dict[str, Any]]] = None):
        # This method is now fully replaced by the direct API calls in DevelopmentTeamService.
        # It can be removed in a future refactor.
        yield "LLM_API_ERROR: llm_client.stream_chat is deprecated. Use direct API calls."