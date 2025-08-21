from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute. This will be run from the root of the active project. Use forward slashes in paths (e.g., 'venv/Scripts/pip')."
        }
    },
    "required": [
        "command"
    ]
}

blueprint = Blueprint(
    id="run_shell_command",
    description="Executes a short-lived, non-interactive shell command from the project's root directory. It will automatically use the project's virtual environment if `python` or `pip` are called. CRITICAL: Do NOT use this for long-running processes like starting a web server (`uvicorn`); the command will time out and fail the mission.",
    parameters=params,
    action_function_name="run_shell_command"
)