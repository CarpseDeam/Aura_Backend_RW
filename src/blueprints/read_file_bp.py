# blueprints/read_file_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The relative path of the file to read."
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="read_file",
    description="Reads the entire content of a specified file and adds it to the context.",
    parameters=params,
    action_function_name="read_file"
)