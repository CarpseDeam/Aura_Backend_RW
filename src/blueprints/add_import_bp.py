# blueprints/add_import_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the Python file to add the import to.",
        },
        "module": {
            "type": "string",
            "description": "The name of the module to import from (e.g., 'os', 'pathlib').",
        },
        "names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional list of specific names to import from the module (e.g., ['Path']). If empty, a simple 'import module' statement will be added."
        }
    },
    "required": ["path", "module"],
}

blueprint = Blueprint(
    id="add_import",
    description="Adds an import statement to the top of a Python file. Handles both 'import module' and 'from module import name' styles. It will not add a duplicate import.",
    parameters=params,
    action_function_name="add_import"
)