# src/providers/openai_provider.py
import openai
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
from .base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=self.api_key)

    def transform_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transformed_tools = []
        for tool in tools:
            transformed_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return transformed_tools

    async def get_chat_response_stream(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                       is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> AsyncGenerator[str, None]:
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": True, # Enable streaming
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            else:
                if is_json:
                    kwargs["response_format"] = {"type": "json_object"}

            stream = await self.client.chat.completions.create(**kwargs)

            tool_call_aggregator = {}
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.tool_calls:
                        # Aggregate tool call chunks
                        for tool_call_chunk in delta.tool_calls:
                            index = tool_call_chunk.index
                            if index not in tool_call_aggregator:
                                tool_call_aggregator[index] = {"name": "", "arguments": ""}
                            if tool_call_chunk.function.name:
                                tool_call_aggregator[index]["name"] += tool_call_chunk.function.name
                            if tool_call_chunk.function.arguments:
                                tool_call_aggregator[index]["arguments"] += tool_call_chunk.function.arguments
                    elif delta.content:
                        # Yield content chunks directly
                        yield delta.content

            # After the stream, process any aggregated tool calls
            if tool_call_aggregator:
                try:
                    # For simplicity, we process the first tool call
                    first_tool_call = tool_call_aggregator[0]
                    tool_output = {
                        "tool_name": first_tool_call["name"],
                        "arguments": json.loads(first_tool_call["arguments"])
                    }
                    yield json.dumps(tool_output)
                except json.JSONDecodeError as e:
                    raw_args = tool_call_aggregator[0].get("arguments", "")
                    error_msg = f"OpenAI JSON parsing error for tool call: {e}. Raw args: '{raw_args}'"
                    print(error_msg)
                    raise RuntimeError(error_msg)

        except openai.APIError as e:
            raise RuntimeError(f"OpenAI API call failed. Status: {e.status_code}. Details: {e.message}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred with OpenAI. Details: {e}")