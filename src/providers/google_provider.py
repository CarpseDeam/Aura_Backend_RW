# src/providers/google_provider.py
import google.generativeai as genai
from typing import List, Dict, Any
import json
from .base_provider import BaseProvider


class GoogleProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            raise ValueError(f"Failed to configure Google AI: {e}")

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                is_json: bool = False) -> str:
        try:
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if is_json else "text/plain",
            )

            response = await model.generate_content_async(
                contents=messages,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            return f"Error: Google API call failed. Details: {e}"