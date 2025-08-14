# src/providers/openai_provider.py
import openai
from typing import List, Dict, Any, Optional
import json
from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            # Add tools to the request if they are provided
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            else:
                # Use JSON mode only if no tools are present
                if is_json:
                    kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)

            response_message = response.choices[0].message

            # Check for a tool call in the response
            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                tool_output = {
                    "tool_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }
                return json.dumps(tool_output)

            # Fallback to text content if no tool call
            content = response_message.content
            return content if content else "Error: OpenAI API returned an empty response."
        except openai.APIError as e:
            return f"Error: OpenAI API call failed. Status: {e.status_code}. Details: {e.message}"
        except Exception as e:
            return f"Error: An unexpected error occurred with OpenAI. Details: {e}"