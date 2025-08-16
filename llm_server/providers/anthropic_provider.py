# src/providers/anthropic_provider.py
import anthropic
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    def _prepare_messages_and_system_prompt(self, messages: List[Dict[str, Any]]) -> (Optional[str],
                                                                                      List[Dict[str, Any]]):
        system_prompt = None
        prepared_messages = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'system':
                system_prompt = msg.get('content')
                prepared_messages = messages[i + 1:]
                break
        else:
            prepared_messages = messages
        return system_prompt, prepared_messages

    def transform_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transformed_tools = []
        for tool in tools:
            transformed_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            })
        return transformed_tools

    async def get_chat_response_stream(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                       is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> \
    AsyncGenerator[str, None]:
        try:
            system_prompt, prepared_messages = self._prepare_messages_and_system_prompt(messages)

            kwargs = {
                "model": model_name,
                "max_tokens": 4096,
                "messages": prepared_messages,
                "temperature": temperature,
                "stream": True,  # Enable streaming
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = {"type": "auto"}

            tool_name = ""
            tool_input_aggregator = ""

            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
                    elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                        tool_input_aggregator += event.delta.partial_json
                    elif event.type == "message_stop" and tool_input_aggregator:
                        try:
                            tool_use_block = next((block for block in (await stream.get_final_message()).content if
                                                   block.type == 'tool_use'), None)
                            if tool_use_block:
                                tool_output = {
                                    "tool_name": tool_use_block.name,
                                    "arguments": json.loads(tool_input_aggregator)  # Use aggregated JSON
                                }
                                yield json.dumps(tool_output)
                        except json.JSONDecodeError as e:
                            error_msg = f"Anthropic JSON parsing error for tool call: {e}. Raw data: '{tool_input_aggregator}'"
                            print(error_msg)
                            raise RuntimeError(error_msg)

        except anthropic.APIError as e:
            raise RuntimeError(f"Anthropic API call failed. Status: {e.status_code}. Details: {e.message}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred with Anthropic. Details: {e}")