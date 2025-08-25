# llm_server/main.py
# llm_server/main.py
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Type, Optional, AsyncGenerator
import json
import logging

from providers import BaseProvider, GoogleProvider, OpenAIProvider, AnthropicProvider, DeepseekProvider

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """
    An async generator that yields structured JSON chunks from the LLM provider.
    This now supports streaming intermediate "thinking" phases for planning.
    """
    try:
        full_response_content = ""
        json_accumulator = ""
        brace_counter = 0
        in_json_block = False
        phases_yielded = set()

        async for chunk in provider.get_chat_response_stream(
                model_name=request.model_name,
                messages=request.messages,
                temperature=request.temperature,
                is_json=request.is_json,
                tools=provider_specific_tools
        ):
            full_response_content += chunk

            if request.is_json:
                json_accumulator += chunk

                if not in_json_block and '{' in json_accumulator:
                    in_json_block = True

                if in_json_block:
                    brace_counter += chunk.count('{')
                    brace_counter -= chunk.count('}')

                    # Only check for phases at the top level of the JSON object
                    if brace_counter == 1:
                        if '"draft_blueprint":' in json_accumulator and 'draft_blueprint' not in phases_yielded:
                            yield json.dumps({"type": "phase",
                                              "content": "Architect is designing the high-level blueprint..."}) + "\n"
                            phases_yielded.add('draft_blueprint')
                        if '"critique":' in json_accumulator and 'critique' not in phases_yielded:
                            yield json.dumps(
                                {"type": "phase",
                                 "content": "Architect is critiquing the blueprint for flaws..."}) + "\n"
                            phases_yielded.add('critique')
                        if '"final_blueprint":' in json_accumulator and 'final_blueprint' not in phases_yielded:
                            yield json.dumps(
                                {"type": "phase",
                                 "content": "Architect is refining the final blueprint..."}) + "\n"
                            phases_yielded.add('final_blueprint')

                if brace_counter <= 0 and in_json_block:
                    in_json_block = False
            else:
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

        if not full_response_content.strip():
            error_message = "The AI model returned an empty response. This may be due to a content filter or an internal model error. Please try again."
            yield json.dumps({"type": "system_log", "content": error_message}) + "\n"
            return

        final_payload = {"final_response": {"reply": full_response_content}}
        yield json.dumps(final_payload) + "\n"

    except Exception as e:
        error_message = f"A critical error occurred in the AI microservice: {e}"
        logger.error(f"ERROR in stream_llm_response: {error_message}", exc_info=True)
        yield json.dumps({"type": "system_log", "content": error_message}) + "\n"


@app.post("/invoke")
async def invoke_llm(
        request: LLMRequest,
        x_provider_api_key: str = Header(...)
):
    """
    Receives a request and invokes the specified LLM provider, streaming the response.
    """
    logger.info("✅ LLM SERVER: /invoke endpoint hit.")
    logger.info(f"Received request for provider: {request.provider_name}, model: {request.model_name}")

    if not x_provider_api_key:
        logger.error("Provider API key is missing from headers.")
        raise HTTPException(status_code=400, detail="Provider API key is missing from headers.")

    provider_class = PROVIDER_MAP.get(request.provider_name)
    if not provider_class:
        logger.error(f"Provider '{request.provider_name}' is not supported.")
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{request.provider_name}' is not supported. Supported providers are: {list(PROVIDER_MAP.keys())}"
        )

    try:
        provider = provider_class(x_provider_api_key)
    except ValueError as e:
        logger.error(f"Failed to initialize provider: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize provider: {e}")

    provider_specific_tools = None
    if request.tools:
        provider_specific_tools = provider.transform_tools_for_provider(request.tools)

    logger.info("Streaming response back to client...")
    return StreamingResponse(
        stream_llm_response(provider, request, provider_specific_tools),
        media_type="application/x-ndjson"
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}