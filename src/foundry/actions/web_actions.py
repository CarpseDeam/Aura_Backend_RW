# foundry/actions/web_actions.py
"""
Contains actions related to interacting with web services and APIs.
"""
import logging
import requests
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def api_request(method: str, url: str, headers: Optional[Dict[str, Any]] = None,
                json_body: Optional[Dict[str, Any]] = None) -> str:
    """
    Performs a generic API request using the requests library.

    Args:
        method: The HTTP method (GET, POST, etc.).
        url: The URL of the endpoint.
        headers: Optional dictionary of request headers.
        json_body: Optional dictionary for the JSON request body.

    Returns:
        A string containing the response status and data, or an error message.
    """
    logger.info(f"Performing API request: {method} {url}")
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_body,
            timeout=30  # Add a reasonable timeout
        )

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Try to parse response as JSON, fall back to text if it fails
        try:
            response_data = response.json()
            response_content = json.dumps(response_data, indent=2)
        except json.JSONDecodeError:
            response_content = response.text

        success_message = (
            f"API Request Successful: {response.status_code} {response.reason}\n"
            f"Response:\n{response_content}"
        )
        return success_message

    except requests.exceptions.HTTPError as e:
        error_message = (
            f"API Request Failed with HTTP Error: {e.response.status_code} {e.response.reason}\n"
            f"Response: {e.response.text}"
        )
        logger.warning(error_message)
        return error_message
    except requests.exceptions.RequestException as e:
        error_message = f"API Request Failed with a network error: {e}"
        logger.error(error_message, exc_info=True)
        return error_message
    except Exception as e:
        error_message = f"An unexpected error occurred during the API request: {e}"
        logger.exception(error_message)
        return error_message