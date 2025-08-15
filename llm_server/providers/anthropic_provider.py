# src/providers/anthropic_provider.py
import anthropic
from typing import List, Dict, Any, Optional
import json
from .base_provider import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    def _prepare_messages_and_system_prompt(self, messages: List[Dict[str, Any]]) -> (Optional[str],
                                                                                      List[Dict[str, Any]]):
        """
        Separates the system prompt from the messages list for Anthropic's API.
        Anthropic requires a top-level 'system' parameter.
        """
        system_prompt = None
        prepared_messages = []

        # Find the first system message, if any
        for i, msg in enumerate(messages):
            if msg.get('role') == 'system':
                system_prompt = msg.get('content')
                # The rest of the messages are the conversation
                prepared_messages = messages[i + 1:]
                break
        else:  # No system message found
            prepared_messages = messages

        # Anthropic requires the conversation to start with a 'user' role.
        # If the first message is not from a user, we may need to adjust, but
        # for Aura's workflow, it should typically be a user message.
        return system_prompt, prepared_messages

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        try:
            system_prompt, prepared_messages = self._prepare_messages_and_system_prompt(messages)

            kwargs = {
                "model": model_name,
                "max_tokens": 4096,  # Anthropic requires max_tokens
                "messages": prepared_messages,
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = {"type": "auto"}

            # Note: Anthropic doesn't have a dedicated JSON mode like OpenAI.
            # The standard way is to instruct it in the prompt to return JSON.
            # The `is_json` flag is therefore less effective here but we pass it.

            response = await self.client.messages.create(**kwargs)

            if response.stop_reason == "tool_use":
                tool_use_block = next((block for block in response.content if block.type == 'tool_use'), None)
                if tool_use_block:
                    tool_output = {
                        "tool_name": tool_use_block.name,
                        "arguments": tool_use_block.input
                    }
                    return json.dumps(tool_output)

            # Fallback to text content if no tool use
            text_content = "".join([block.text for block in response.content if block.type == 'text'])
            return text_content if text_content else "Error: Anthropic API returned an empty response."

        except anthropic.APIError as e:
            return f"Error: Anthropic API call failed. Status: {e.status_code}. Details: {e.message}"
        except Exception as e:
            return f"Error: An unexpected error occurred with Anthropic. Details: {e}"