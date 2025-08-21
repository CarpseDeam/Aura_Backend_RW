# blueprints/create_package_init_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The path to the directory that should be initialized as a Python package.",
        }
    },
    "required": ["path"],
}

blueprint = Blueprint(
    id="create_package_init",
    description="Creates an `__init__.py` file in a specified directory to turn it into a Python package. This is essential for enabling relative imports between modules in that directory.",
    parameters=params,
    action_function_name="create_package_init"
)