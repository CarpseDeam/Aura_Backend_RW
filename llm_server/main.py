# llm_server/main.py
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Type, Optional, AsyncGenerator
import json

from providers import BaseProvider, GoogleProvider, OpenAIProvider, AnthropicProvider, DeepseekProvider

app = FastAPI(
    title="Aura LLM Server",
    description="A dedicated microservice for handling LLM API calls.",
    version="1.0.0",
)

PROVIDER_MAP: Dict[str, Type[BaseProvider]] = {
    "google": GoogleProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepseekProvider,
}

class LLMRequest(BaseModel):
    provider_name: str
    model_name: str
    messages: List[Dict[str, Any]]
    temperature: float
    is_json: bool = False
    tools: Optional[List[Dict[str, Any]]] = None

async def stream_llm_response(
    provider: BaseProvider,
    request: LLMRequest,
    provider_specific_tools: Optional[List[Dict[str, Any]]]
) -> AsyncGenerator[str, None]:
    """An async generator that yields chunks from the LLM provider."""
    try:
        full_response = ""
        async for chunk in provider.get_chat_response_stream(
            model_name=request.model_name,
            messages=request.messages,
            temperature=request.temperature,
            is_json=request.is_json,
            tools=provider_specific_tools
        ):
            full_response += chunk
            yield chunk

        # If the response was supposed to be JSON, we wrap the final result.
        # This allows the client to accumulate chunks and then parse the final JSON.
        if request.is_json or (request.tools and '"tool_name":' in full_response):
            final_output = json.dumps({"reply": full_response})
            yield final_output
        else:
            # For regular text, we can just send the raw chunks.
            # To signal the end and wrap it for the client, we can send a final JSON.
            final_output = json.dumps({"reply": full_response})
            yield final_output

    except Exception as e:
        error_message = f"Error during streaming: {e}"
        print(error_message)
        # Yield a JSON error message so the client can handle it gracefully.
        yield json.dumps({"error": error_message})


@app.post("/invoke")
async def invoke_llm(
    request: LLMRequest,
    x_provider_api_key: str = Header(...)
):
    """
    Receives a request and invokes the specified LLM provider, streaming the response.
    """
    if not x_provider_api_key:
        raise HTTPException(status_code=400, detail="Provider API key is missing from headers.")

    provider_class = PROVIDER_MAP.get(request.provider_name)
    if not provider_class:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{request.provider_name}' is not supported. Supported providers are: {list(PROVIDER_MAP.keys())}"
        )

    try:
        provider = provider_class(x_provider_api_key)
    except ValueError as e:
         raise HTTPException(status_code=500, detail=f"Failed to initialize provider: {e}")

    provider_specific_tools = None
    if request.tools:
        provider_specific_tools = provider.transform_tools_for_provider(request.tools)

    # We now return a StreamingResponse, which will stream the output of our async generator.
    return StreamingResponse(
        stream_llm_response(provider, request, provider_specific_tools),
        media_type="application/x-ndjson" # Use newline-delimited JSON for streaming chunks
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}