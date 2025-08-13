from typing import Dict
from fastapi import FastAPI
from src.api.auth import router as auth_router
from src.api.keys import router as keys_router
from src.api.websockets import router as websocket_router
from src.api.agent import router as agent_router

app = FastAPI(
    title="Aura Web Platform",
    description="The agentic core and user management services for the Aura platform.",
    version="1.0.0",
)

# Include the routers from the api modules with appropriate prefixes and tags
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(keys_router, prefix="/api-keys", tags=["API Keys"])
app.include_router(websocket_router, tags=["WebSockets"])
app.include_router(agent_router, prefix="/agent", tags=["Aura Agent"])


@app.get("/", response_model=Dict[str, str], tags=["Root"])
async def read_root() -> Dict[str, str]:
    """
    Root GET endpoint.

    Provides a simple welcome message to verify that the service is running.

    Returns:
        Dict[str, str]: A dictionary containing a welcome message.
    """
    return {"message": "Welcome to the Aura API Command Center"}