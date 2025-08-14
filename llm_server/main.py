# llm_server/main.py
import os
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any

# This import will now work correctly because of our new Dockerfile setup.
from src.providers import GoogleProvider, OpenAIProvider

app = FastAPI(
    title="Aura LLM Server",
    description="A dedicated microservice for handling LLM API calls.",
    version="1.0.0",
)

class LLMRequest(BaseModel):
    provider_name: str
    model_name: str
    messages: List[Dict[str, Any]]
    temperature: float
    is_json: bool = False

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

    provider = None
    try:
        if request.provider_name == "google":
            provider = GoogleProvider(x_provider_api_key)
        elif request.provider_name == "openai":
            provider = OpenAIProvider(x_provider_api_key)
        # Add other providers here as they are implemented
        else:
            raise HTTPException(status_code=400, detail=f"Provider '{request.provider_name}' is not supported.")
    except ValueError as e:
         raise HTTPException(status_code=500, detail=f"Failed to initialize provider: {e}")


    response_text = await provider.get_chat_response(
        model_name=request.model_name,
        messages=request.messages,
        temperature=request.temperature,
        is_json=request.is_json
    )

    if response_text.startswith("Error:"):
        # Pass the error from the provider back to the main app
        raise HTTPException(status_code=500, detail=response_text)

    return {"reply": response_text}

@app.get("/health")
def health_check():
    return {"status": "ok"}