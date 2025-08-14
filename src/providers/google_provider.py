# src/providers/google_provider.py
import google.generativeai as genai
from typing import List, Dict, Any, Optional
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
        """
        Recursively traverses a JSON schema dict and uppercases 'type' values
        for Gemini compatibility.
        """
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
        """Transforms the tool schema to meet Gemini's specific requirements (uppercase types)."""
        if not tools:
            return []

        transformed_tools = []
        for tool in tools:
            tool_copy = copy.deepcopy(tool)
            if 'parameters' in tool_copy:
                tool_copy['parameters'] = self._uppercase_schema_types(tool_copy['parameters'])
            transformed_tools.append(tool_copy)
        return transformed_tools

    async def get_chat_response(self, model_name: str, messages: List[Dict[str, Any]], temperature: float,
                                is_json: bool = False, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        try:
            # Note: Transformation is now expected to happen in llm-server before this call
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