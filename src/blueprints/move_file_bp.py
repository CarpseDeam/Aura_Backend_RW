# blueprints/move_file_bp.py
from src.foundry.blueprints import Blueprint

# The schema that defines the parameters for the LLM.
params = {
    "type": "object",
    "properties": {
        "source_path": {
            "type": "string",
            "description": "The original path of the file to move.",
        },
        "destination_path": {
            "type": "string",
            "description": "The new path for the file, which can include a new filename to perform a rename.",
        }
    },
    "required": ["source_path", "destination_path"],
}

# The blueprint object that Aura's Foundry will discover.
blueprint = Blueprint(
    id="move_file",
    description="Moves a file from a source path to a destination path. Can also be used to rename files. This will overwrite a file at the destination if it exists.",
    parameters=params,
    action_function_name="move_file"  # This must match the function in the action file.
)