# blueprints/api_request_bp.py
from src.foundry.blueprints import Blueprint

params = {
    "type": "object",
    "properties": {
        "method": {
            "type": "string",
            "description": "The HTTP method to use (e.g., 'GET', 'POST', 'PUT', 'DELETE').",
        },
        "url": {
            "type": "string",
            "description": "The URL of the API endpoint to request.",
        },
        "headers": {
            "type": "object",
            "description": "Optional. A dictionary of headers to send with the request.",
        },
        "json_body": {
            "type": "object",
            "description": "Optional. A JSON object (dictionary) to send as the body of a POST or PUT request.",
        },
    },
    "required": ["method", "url"],
}

blueprint = Blueprint(
    id="api_request",
    description="Makes a generic HTTP request to an API endpoint. Useful for fetching data or interacting with web services.",
    parameters=params,
    action_function_name="api_request"
)