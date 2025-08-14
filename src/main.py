# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

from src.api.auth import router as auth_router
from src.api.keys import router as keys_router
from src.api.websockets import router as websocket_router
from src.api.agent import router as agent_router
from src.api.assignments import router as assignments_router
from src.api.missions import router as missions_router

app = FastAPI(
    title="Aura Web Platform",
    description="The agentic core and user management services for the Aura platform.",
    version="1.0.0",
)

# --- THIS IS THE CRITICAL FIX ---
# We are temporarily allowing all origins to confirm that CORS is the issue.
# The wildcard "*" tells the browser that any domain is allowed to make requests.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with prefixes and tags
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(keys_router, prefix="/api-keys", tags=["Provider Keys"])
app.include_router(assignments_router, prefix="/api/assignments", tags=["Model Assignments"])
app.include_router(missions_router, prefix="/api", tags=["Mission Control"])
app.include_router(websocket_router, tags=["WebSockets"])
app.include_router(agent_router, prefix="/agent", tags=["Aura Agent"])


@app.get("/", response_model=Dict[str, str], tags=["Root"])
async def read_root() -> Dict[str, str]:
    """Root GET endpoint."""
    return {"message": "Welcome to the Aura API Command Center"}