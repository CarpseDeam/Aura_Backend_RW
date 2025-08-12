# src/main.py
from typing import Dict
from fastapi import FastAPI
from src.api import auth, keys
from src.db.database import Base, engine

app = FastAPI(
    title="Aura Web Backend",
    description="The agentic core and user management services for the Aura platform.",
    version="0.1.0",
)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(keys.router)

@app.get("/", response_model=Dict[str, str], tags=["Root"])
async def read_root() -> Dict[str, str]:
    return {"message": "Welcome to the Aura API"}