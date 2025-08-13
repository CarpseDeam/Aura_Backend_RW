# blueprints/delete_file_bp.py
from src.foundry.blueprints import Blueprint

# The schema that defines the parameters for the LLM.
params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The full path of the file to be deleted.",
        }
    },
    "required": ["path"],
}

# The blueprint object that Aura's Foundry will discover.
blueprint = Blueprint(
    id="delete_file",
    description="Deletes a specified file from the filesystem. This action is irreversible, so be certain.",
    parameters=params,
    action_function_name="delete_file"  # This name must match the function in the action file.
)