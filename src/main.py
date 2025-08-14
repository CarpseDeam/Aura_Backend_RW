# src/main.py
import sys
import traceback

# --- BLACK BOX RECORDER ---
# This block will catch the silent crash and force the error into the logs.
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from typing import Dict

    # This chain of imports is what is crashing. One of these files
    # is triggering a fatal error, most likely when src.core.config runs.
    from src.api.auth import router as auth_router
    from src.api.keys import router as keys_router
    from src.api.websockets import router as websocket_router
    from src.api.agent import router as agent_router
    from src.api.assignments import router as assignments_router
    from src.api.missions import router as missions_router
    from src.core.config import settings

except Exception as e:
    # If the app crashes on import, this will print the truth to the logs.
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
    print("!!!    A FATAL ERROR OCCURRED DURING APP STARTUP     !!!", file=sys.stderr)
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=sys.stderr)
    print(f"Error Type: {type(e).__name__}", file=sys.stderr)
    print(f"Error Details: {e}", file=sys.stderr)
    print("--------------------- FULL TRACEBACK ---------------------", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("----------------------------------------------------------", file=sys.stderr)
    print("This is likely a missing environment variable.", file=sys.stderr)
    print("Please verify DATABASE_URL, JWT_SECRET_KEY, and ENCRYPTION_KEY in Railway.", file=sys.stderr)
    # Exit with an error code to make sure the process stops.
    sys.exit(1)
# --- END OF RECORDER ---


app = FastAPI(
    title="Aura Web Platform",
    description="The agentic core and user management services for the Aura platform.",
    version="1.0.0",
)

origins = [
    "https://snowballannotation.com",
    "https://www.snowballannotation.com",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:5500"
]

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