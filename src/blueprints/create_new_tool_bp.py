# blueprints/create_new_tool_bp.py
from src.foundry.blueprints import Blueprint

# This schema tells the LLM to provide a 'tool_parameters' list.
params = {
    "type": "object",
    "properties": {
        "tool_name": {
            "type": "string",
            "description": "The unique ID for the new tool (e.g., 'rename_file').",
        },
        "description": {
            "type": "string",
            "description": "A clear, user-facing description of what the new tool does.",
        },
        "tool_parameters": {
            "type": "array",
            "description": "A list of parameter objects for the new tool. Each object should have 'name', 'type', and 'description' keys.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The parameter name."},
                    "type": {"type": "string", "description": "The JSON schema type (e.g., 'string', 'integer')."},
                    "description": {"type": "string", "description": "The parameter description."}
                },
                "required": ["name", "type", "description"]
            }
        },
        "action_code": {
            "type": "string",
            "description": "A string containing the complete Python code for the action function, including necessary imports."
        }
    },
    "required": ["tool_name", "description", "tool_parameters", "action_code"],
}

blueprint = Blueprint(
    id="create_new_tool",
    description="Meta-Tool: Creates a new, fully functional tool for Aura by generating BOTH a blueprint file and its corresponding action file. The application must be restarted to load the new tool.",
    parameters=params,
    action_function_name="create_new_tool"
)