from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import json

from src.core.websockets import websocket_manager
from src.db import models, crud
from src.db.database import get_db
from src.core import config
from src.schemas import token

router = APIRouter()


async def get_current_user_ws(
        websocket: WebSocket,
        token_str: str | None = Query(None, alias="token"),
        db: Session = Depends(get_db),
) -> models.User | None:
    """
    A dependency to authenticate users for WebSocket connections.
    It reads the JWT token from a URL query parameter.
    """
    if token_str is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
        return None

    try:
        payload = jwt.decode(
            token_str, config.settings.JWT_SECRET_KEY, algorithms=[config.settings.ALGORITHM]
        )
        email: str | None = payload.get("sub")
        if email is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            return None
        token_data = token.TokenData(email=email)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return None

    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
        return None

    return user


@router.websocket("/ws/command_deck")
async def websocket_endpoint(
        websocket: WebSocket,
        user: models.User = Depends(get_current_user_ws)
):
    """
    Handles WebSocket connections, now with a heartbeat mechanism to prevent
    idle timeouts from network infrastructure.
    """
    if not user:
        return

    user_id = str(user.id)
    client_id = "command_deck"
    await websocket_manager.connect(websocket, user_id, client_id)

    try:
        await websocket_manager.send_to_client(
            {"type": "internal_ws_status", "content": "connected"}, user_id, client_id
        )

        while True:
            data_text = await websocket.receive_text()
            try:
                # --- THE FIX: Heartbeat Handling ---
                # The frontend will send `{"type": "ping"}` periodically.
                # We catch it, do nothing, and continue listening.
                # This keeps the connection alive.
                data = json.loads(data_text)
                if data.get("type") == "ping":
                    continue
            except json.JSONDecodeError:
                # Not a JSON message, just log it and ignore
                print(f"Received non-JSON message from User '{user_id}': {data_text}")
                continue

            # In production, we don't need to echo messages back.
            # This can be removed later.
            print(f"Received message from User '{user_id}', Client '{client_id}': {data_text}")

    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id, client_id)
        print(f"User '{user_id}' disconnected from WebSocket.")
    except Exception as e:
        print(f"An unexpected error occurred in WebSocket for user '{user_id}': {e}")
        websocket_manager.disconnect(user_id, client_id)