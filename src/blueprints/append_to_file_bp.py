# blueprints/append_to_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path of the file to append content to."
        },
        "content": {
            "type": "string",
            "description": "The content to append to the end of the file."
        }
    },
    "required": ["path", "content"],
}

blueprint = Blueprint(
    id="append_to_file",
    description="Appends content to the end of an existing file. This is the preferred way to add non-function code blocks like `if __name__ == '__main__'`.",
    parameters=params,
    action_function_name="append_to_file"
)