from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.db.database import engine
from src.db import models
# --- CORRECTED IMPORTS ---
# We now import the specific modules that actually exist.
from src.api import auth, agent, keys, assignments, missions, websockets

# This creates your database tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Aura Backend",
    description="Backend services for the Aura AI development environment.",
    version="1.0.0"
)

# --- CORS Middleware ---
origins = [
    "https://aura-frontend-two.vercel.app",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# --- CORRECTED ROUTER INCLUDES ---
# We now use the 'router' object from the 'keys' and 'assignments' modules.
app.include_router(keys.router, prefix="/api-keys", tags=["Settings"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["Settings"])
app.include_router(missions.router, prefix="/api/missions", tags=["Missions"])
app.include_router(websockets.router, tags=["WebSockets"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])


# --- Static Files Mount ---
# This serves your frontend from the 'static' directory.
app.mount("/", StaticFiles(directory="static", html=True), name="static")