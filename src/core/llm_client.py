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
        self.load_assignments()
        print(f"[LLMClient] Client initialized. Will connect to LLM server at {self.llm_server_url}")

    def load_assignments(self):
        """Loads role assignments and temperatures from JSON, with smart, self-healing defaults."""
        # Step 1: Load the hard-coded defaults from the default config file.
        try:
            with open(self.default_assignments_file, 'r') as f:
                default_config = json.load(f)
            default_assignments = default_config.get("role_assignments", {})
            default_temperatures = default_config.get("role_temperatures", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(
                f"[LLMClient] CRITICAL: Could not load default_role_assignments.json: {e}. Cannot proceed with defaults.")
            # In a real-world scenario, you might have an emergency hardcoded fallback here.
            # For now, we'll assume the file is part of the application distribution.
            default_assignments = {}
            default_temperatures = {}

        # Step 2: Load the user's custom settings.
        loaded_assignments = {}
        loaded_temperatures = {}
        if self.assignments_file.exists():
            try:
                with open(self.assignments_file, 'r') as f:
                    user_config = json.load(f)
                loaded_assignments = user_config.get("role_assignments", {})
                loaded_temperatures = user_config.get("role_temperatures", {})
            except (json.JSONDecodeError, TypeError) as e:
                print(
                    f"[LLMClient] Warning: Could not parse role_assignments.json: {e}. Will use defaults and attempt to repair.")

        # Step 3: Merge user settings over the defaults.
        final_assignments = default_assignments.copy()
        final_temperatures = default_temperatures.copy()

        if isinstance(loaded_assignments, dict):
            final_assignments.update(loaded_assignments)
        if isinstance(loaded_temperatures, dict):
            final_temperatures.update(loaded_temperatures)

        # Step 4: Self-heal any missing or invalid entries by restoring from the defaults.
        for role, model in final_assignments.items():
            if not model and role in default_assignments:
                final_assignments[role] = default_assignments[role]

        for role in default_assignments:
            if role not in final_assignments:
                final_assignments[role] = default_assignments[role]

        self.role_assignments = final_assignments
        self.role_temperatures = final_temperatures

        # Step 5: Save the potentially repaired config back to the user's file.
        self.save_assignments()

    def save_assignments(self):
        """Saves the current role assignments and temperatures to the user's JSON file."""
        config_data = {
            "role_assignments": self.role_assignments,
            "role_temperatures": self.role_temperatures
        }
        with open(self.assignments_file, 'w') as f:
            json.dump(config_data, f, indent=4)

    async def get_available_models(self) -> dict:
        """Fetches the list of available models from the LLM server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.llm_server_url}/get_available_models", timeout=5) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"[LLMClient] Error getting models from server: {response.status}")
                        return {}
        except Exception as e:
            print(f"[LLMClient] Could not connect to LLM server to get models: {e}")
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
        return self.role_temperatures.get(role, 0.7)

    def get_model_for_role(self, role: str) -> tuple[str | None, str | None]:
        key = self.role_assignments.get(role, self.role_assignments.get("chat"))
        if not key or "/" not in key: return None, None
        provider, model_name = key.split('/', 1)
        return provider, model_name

    async def stream_chat(self, provider: str, model: str, prompt: str, role: str = None,
                          image_bytes: Optional[bytes] = None, image_media_type: str = "image/png",
                          history: Optional[List[Dict[str, Any]]] = None):
        """Streams a chat response from the LLM server."""
        temperature = self.get_role_temperature(role) if role else 0.7
        image_b64 = base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None

        payload = {
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "image_b64": image_b64,
            "media_type": image_media_type,
            "history": history or []
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.llm_server_url}/stream_chat", json=payload, timeout=300) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                yield line.decode('utf-8')
                    else:
                        error_text = await response.text()
                        yield f"LLM_API_ERROR: Failed to stream from server. Status: {response.status}, Details: {error_text}"
        except Exception as e:
            yield f"LLM_API_ERROR: Could not connect to LLM server. Is it running? Details: {e}"