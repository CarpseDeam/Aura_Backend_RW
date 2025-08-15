# src/providers/deepseek_provider.py
import openai  # DeepSeek uses an OpenAI-compatible API
from typing import List, Dict, Any, Optional
import json
from .base_provider import BaseProvider


class DeepseekProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1"
        )

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            else:
                if is_json:
                    kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)

            response_message = response.choices[0].message

            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                tool_output = {
                    "tool_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }
                return json.dumps(tool_output)

            content = response_message.content
            return content if content else "Error: DeepSeek API returned an empty response."
        except openai.APIError as e:
            return f"Error: DeepSeek API call failed. Status: {e.status_code}. Details: {e.message}"
        except Exception as e:
            return f"Error: An unexpected error occurred with DeepSeek. Details: {e}"