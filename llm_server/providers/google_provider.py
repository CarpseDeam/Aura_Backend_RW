# llm_server/providers/google_provider.py
import google.generativeai as genai
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import copy
from .base_provider import BaseProvider


class GoogleProvider(BaseProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            raise ValueError(f"Failed to configure Google AI: {e}")

    def _uppercase_schema_types(self, schema: Any) -> Any:
        if isinstance(schema, dict):
            new_dict = {}
            for key, value in schema.items():
                if key == 'type' and isinstance(value, str):
                    new_dict[key] = value.upper()
                else:
                    new_dict[key] = self._uppercase_schema_types(value)
            return new_dict
        elif isinstance(schema, list):
            return [self._uppercase_schema_types(item) for item in schema]
        return schema

    def transform_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tools:
            return []

        function_declarations = []
        for tool in tools:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": self._uppercase_schema_types(tool.get("parameters", {}))
            })

        return [{"function_declarations": function_declarations}]

    async def get_chat_response_stream(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                       is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> \
            AsyncGenerator[str, None]:
        try:
            system_prompt = None
            conversation_messages = []
            for msg in messages:
                if msg.get('role') == 'system' and system_prompt is None:
                    system_prompt = msg.get('content', '')
                else:
                    conversation_messages.append(msg)

            prepared_messages = []
            for msg in conversation_messages:
                role = msg.get("role")
                content = msg.get("content")
                if not (role and content): continue
                if role == "assistant": role = "model"
                if role == "system": continue
                if role not in ["user", "model"]: role = "user"
                prepared_messages.append({"role": role, "parts": [{"text": content}]})

            model = genai.GenerativeModel(
                model_name,
                tools=tools,
                system_instruction=system_prompt
            )
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if is_json and not tools else "text/plain",
            )

            response = await model.generate_content_async(
                contents=prepared_messages,
                generation_config=generation_config,
                stream=True  # Enable streaming
            )

            full_tool_call = None
            async for chunk in response:
                if chunk.candidates and chunk.candidates[0].content.parts:
                    part = chunk.candidates[0].content.parts[0]
                    if part.function_call:
                        # Gemini sends the full tool call in one chunk
                        full_tool_call = {
                            "tool_name": part.function_call.name,
                            "arguments": dict(part.function_call.args)
                        }
                        break
                    elif hasattr(part, 'text'):
                        yield part.text

            if full_tool_call:
                yield json.dumps(full_tool_call)

        except Exception as e:
            raise RuntimeError(f"Google API call failed. Details: {e}")

