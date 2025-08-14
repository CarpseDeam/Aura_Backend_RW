# src/providers/google_provider.py
import google.generativeai as genai
from typing import List, Dict, Any, Optional
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
                                is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        try:
            model = genai.GenerativeModel(model_name, tools=tools)
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if is_json and not tools else "text/plain",
            )

            response = await model.generate_content_async(
                contents=messages,
                generation_config=generation_config
            )

            # Check for a tool call in the response
            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                if part.function_call:
                    tool_call = {
                        "tool_name": part.function_call.name,
                        "arguments": dict(part.function_call.args)
                    }
                    return json.dumps(tool_call)

            # Fallback to text if no tool call
            return response.text
        except Exception as e:
            return f"Error: Google API call failed. Details: {e}"