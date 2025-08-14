# src/providers/openai_provider.py
import openai
from typing import List, Dict, Any
import json
from .base_provider import BaseProvider

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float, is_json: bool = False) -> str:
        try:
            response_format = {"type": "json_object"} if is_json else {"type": "text"}
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                response_format=response_format
            )
            content = response.choices[0].message.content
            return content if content else "Error: OpenAI API returned an empty response."
        except openai.APIError as e:
            return f"Error: OpenAI API call failed. Status: {e.status_code}. Details: {e.message}"
        except Exception as e:
            return f"Error: An unexpected error occurred with OpenAI. Details: {e}"