# blueprints/copy_file_bp.py
from src.foundry.blueprints import Blueprint

# The schema that defines the parameters for the LLM.
params = {
    "type": "object",
    "properties": {
        "source_path": {
            "type": "string",
            "description": "The path of the file to copy.",
        },
        "destination_path": {
            "type": "string",
            "description": "The path where the copy will be created. You can specify a new filename.",
        }
    },
    "required": ["source_path", "destination_path"],
}

# The blueprint object that Aura's Foundry will discover.
blueprint = Blueprint(
    id="copy_file",
    description="Copies a file from a source path to a destination path. This will overwrite a file at the destination if it exists.",
    parameters=params,
    action_function_name="copy_file"  # This must match the function in the action file.
)