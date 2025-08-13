# blueprints/index_project_context_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "The root directory to start scanning from. Defaults to the current directory.",
        }
    },
    "required": [],
}

blueprint = Blueprint(
    id="index_project_context",
    description="Scans the project, breaks down Python files into functions and classes, and stores their source code in a vector database for long-term contextual awareness (RAG).",
    parameters=params,
    action_function_name="index_project_context"
)