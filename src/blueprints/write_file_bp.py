# blueprints/write_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path of the file to write to."
        },
        "content": {
            "type": "string",
            "description": "The content to write into the file. Use this for pre-defined content. If you use this, do not use `task_description`."
        },
        "task_description": {
            "type": "string",
            "description": "A detailed, clear, and specific description of the code to be generated for the file. Use this ONLY when you want the AI to generate code. If used, `content` should be empty."
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="write_file",
    description="The primary tool for writing files. It can write pre-defined content directly, or it can generate code via an AI if a `task_description` is provided instead of `content`. It creates directories if needed and overwrites the file if it exists.",
    parameters=params,
    action_function_name="write_file"
)