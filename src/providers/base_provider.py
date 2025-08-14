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

    def transform_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        An optional method to transform the generic tool schema into a
        provider-specific format. By default, it returns the tools unchanged.
        """
        return tools