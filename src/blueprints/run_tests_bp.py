# src/blueprints/run_tests_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {},
    "required": []
}

blueprint = Blueprint(
    id="run_tests",
    description="Executes the project's test suite using pytest from within the project's virtual environment. It will automatically discover and run all tests. This should be the final step in any testing or QA plan.",
    parameters=params,
    action_function_name="run_tests"
)