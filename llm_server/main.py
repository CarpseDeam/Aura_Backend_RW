# llm_server/main.py
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Type, Optional

# This import will now work correctly because of our new Dockerfile setup.
from src.providers import BaseProvider, GoogleProvider, OpenAIProvider, AnthropicProvider, DeepseekProvider

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

@app.post("/invoke")
async def invoke_llm(
    request: LLMRequest,
    x_provider_api_key: str = Header(...)
):
    """
    Receives a request and invokes the specified LLM provider.
    The provider-specific API key is passed securely in the headers.
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

    # Transform tools for the specific provider if they exist
    provider_specific_tools = None
    if request.tools:
        provider_specific_tools = provider.transform_tools_for_provider(request.tools)

    response_text = await provider.get_chat_response(
        model_name=request.model_name,
        messages=request.messages,
        temperature=request.temperature,
        is_json=request.is_json,
        tools=provider_specific_tools
    )

    if response_text.startswith("Error:"):
        raise HTTPException(status_code=500, detail=response_text)

    return {"reply": response_text}

@app.get("/health")
def health_check():
    return {"status": "ok"}