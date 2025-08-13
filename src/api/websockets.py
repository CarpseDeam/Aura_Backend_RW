from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt

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


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        client_id: str,
        user: models.User = Depends(get_current_user_ws)
):
    """
    Handles WebSocket connections, now using a query-param-aware authenticator.
    A unique client_id is expected for each connecting window.
    """
    if not user:
        # The dependency will have already closed the connection if auth fails.
        return

    user_id = str(user.id)
    await websocket_manager.connect(websocket, user_id, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message from User '{user_id}', Client '{client_id}': {data}")
            # For now, just echo the message back to demonstrate the connection.
            await websocket_manager.send_to_client(
                {"sender": "Aura", "message": f"Acknowledged: {data}"}, user_id, client_id
            )

    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id, client_id)