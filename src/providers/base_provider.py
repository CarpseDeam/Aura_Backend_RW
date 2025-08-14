# src/providers/base_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseProvider(ABC):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key

    @abstractmethod
    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float, is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        pass