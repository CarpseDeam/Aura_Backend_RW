from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

from src.api.auth import router as auth_router
from src.api.keys import router as keys_router
from src.api.websockets import router as websocket_router
from src.api.agent import router as agent_router
from src.api.assignments import router as assignments_router
from src.api.missions import router as missions_router
from src.db.database import Base, engine # Import Base and engine

# --- NEW FUNCTION TO CREATE DATABASE TABLES ---
def create_db_and_tables():
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully.")
    except Exception as e:
        print(f"An error occurred while creating database tables: {e}")

# --- END OF NEW FUNCTION ---

app = FastAPI(
    title="Aura Web Platform",
    description="The agentic core and user management services for the Aura platform.",
    version="1.0.0",
)

# --- NEW: RUN TABLE CREATION ON STARTUP ---
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
# --- END OF NEW STARTUP EVENT ---


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