# blueprints/stream_and_write_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The relative path of the file to be written (e.g., 'src/main.py', 'docs/readme.md')."
        },
        "task_description": {
            "type": "string",
            "description": "A detailed, clear, and specific description of the code to be generated for the file. This will be used as the prompt for the Coder AI."
        }
    },
    "required": ["path", "task_description"],
}

blueprint = Blueprint(
    id="stream_and_write_file",
    description="The primary tool for generating code. It takes a path and a detailed task description, streams the generated code to the user in real-time, and then saves the final result to the specified file. This is the REQUIRED tool for all new code generation.",
    parameters=params,
    action_function_name="stream_and_write_file"
)