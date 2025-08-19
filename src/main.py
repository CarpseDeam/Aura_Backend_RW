from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import engine
from src.db import models
from src.api import auth, agent, keys, assignments, missions, websockets

# This creates your database tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Aura Backend",
    description="Backend services for the Aura AI development environment.",
    version="1.0.0"
)

# --- THE FIX: A robust, regex-based CORS configuration ---
# This pattern allows your main domain, any Vercel preview URLs, and localhost.
# It's more flexible and less prone to errors than a static list.
origins_regex = r"https?://(.*\.)?snowballannotation\.com|https?://localhost(:\d+)?|https?://127\.0\.0\.1(:\d+)?|https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=origins_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(keys.router, prefix="/api-keys", tags=["Settings"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["Settings"])
app.include_router(missions.router, prefix="/api/missions", tags=["Missions"])
app.include_router(websockets.router, tags=["WebSockets"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])